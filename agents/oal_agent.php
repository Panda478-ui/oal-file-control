<?php
/**
 * File Clear — agente remoto
 *
 * 1) Sube este archivo a la carpeta del sitio (ej. /lab_sys/oal_agent.php)
 * 2) Sube también el archivo "oal-lab-clean" en la misma carpeta
 * 3) Conecta cualquier dominio desde https://oal-file-control.onrender.com
 *
 * Autorización: token "oal-lab-clean" O presencia del archivo oal-lab-clean.
 */

declare(strict_types=1);

header('Access-Control-Allow-Origin: *');
header('Access-Control-Allow-Methods: GET, POST, OPTIONS');
header('Access-Control-Allow-Headers: Content-Type, X-OAL-Token, ngrok-skip-browser-warning');

if (($_SERVER['REQUEST_METHOD'] ?? 'GET') === 'OPTIONS') {
    http_response_code(204);
    exit;
}

const OAL_AGENT_TOKEN = 'oal-lab-clean';
const SKIP_NAMES = ['.', '..', '.git'];

$root = realpath(__DIR__);
if ($root === false) {
    json_out(500, ['error' => 'No se pudo resolver el directorio raíz']);
}

$token = $_GET['token']
    ?? $_SERVER['HTTP_X_OAL_TOKEN']
    ?? '';

$body = [];
$raw = file_get_contents('php://input');
if (is_string($raw) && $raw !== '') {
    $decoded = json_decode($raw, true);
    if (is_array($decoded)) {
        $body = $decoded;
        if ($token === '' && isset($body['token'])) {
            $token = (string) $body['token'];
        }
    }
}

if (!is_authorized((string) $token, $root)) {
    json_out(401, [
        'error' => 'No autorizado. Coloca el archivo oal-lab-clean junto al agente o usa token=oal-lab-clean',
    ]);
}

$action = $_GET['action'] ?? ($body['action'] ?? 'files');
$method = $_SERVER['REQUEST_METHOD'] ?? 'GET';

if ($action === 'ping') {
    json_out(200, [
        'ok' => true,
        'agent' => 'oal_agent',
        'version' => '2.0',
        'root' => $root,
        'auth' => 'oal-lab-clean',
    ]);
}

if ($action === 'files' && $method === 'GET') {
    $rel = (string) ($_GET['path'] ?? '');
    try {
        json_out(200, list_entries($root, $rel));
    } catch (Throwable $e) {
        json_out(400, ['error' => $e->getMessage()]);
    }
}

if ($action === 'eliminar' && $method === 'POST') {
    $names = $body['files'] ?? [];
    $current = (string) ($body['path'] ?? '');
    if (!is_array($names)) {
        json_out(400, ['error' => 'Envía {"files":["archivo"],"path":""}']);
    }
    try {
        json_out(200, delete_files($root, $names, $current));
    } catch (Throwable $e) {
        json_out(400, ['error' => $e->getMessage()]);
    }
}

json_out(404, ['error' => 'Acción no encontrada. Usa action=files|eliminar|ping']);

function is_authorized(string $token, string $root): bool
{
    $token = trim($token);
    if ($token !== '' && hash_equals(OAL_AGENT_TOKEN, $token)) {
        return true;
    }

    foreach (['oal-lab-clean', '.oal-lab-clean'] as $name) {
        $marker = $root . DIRECTORY_SEPARATOR . $name;
        if (!is_file($marker)) {
            continue;
        }
        $content = trim((string) file_get_contents($marker));
        // Archivo vacío o con la clave: permite conectar desde cualquier dominio
        if ($content === '' || $content === OAL_AGENT_TOKEN) {
            return true;
        }
        if ($token !== '' && hash_equals($content, $token)) {
            return true;
        }
    }

    return false;
}

function json_out(int $status, array $payload): void
{
    http_response_code($status);
    header('Content-Type: application/json; charset=utf-8');
    header('Cache-Control: no-store');
    echo json_encode($payload, JSON_UNESCAPED_UNICODE | JSON_UNESCAPED_SLASHES);
    exit;
}

function human_size(int $bytes): string
{
    $units = ['B', 'KB', 'MB', 'GB'];
    $size = (float) $bytes;
    foreach ($units as $unit) {
        if ($size < 1024 || $unit === 'GB') {
            return $unit === 'B' ? ((string) (int) $size) . " $unit" : number_format($size, 1) . " $unit";
        }
        $size /= 1024;
    }
    return $bytes . ' B';
}

function normalize_rel(string $rel): string
{
    $rel = str_replace('\\', '/', trim($rel));
    $rel = trim($rel, '/');
    if ($rel === '') {
        return '';
    }
    $parts = [];
    foreach (explode('/', $rel) as $part) {
        if ($part === '' || $part === '.') {
            continue;
        }
        if ($part === '..' || in_array($part, SKIP_NAMES, true)) {
            throw new InvalidArgumentException('Ruta no permitida');
        }
        $parts[] = $part;
    }
    return implode('/', $parts);
}

function resolve_dir(string $root, string $rel): string
{
    $rel = normalize_rel($rel);
    $target = $rel === '' ? $root : $root . DIRECTORY_SEPARATOR . str_replace('/', DIRECTORY_SEPARATOR, $rel);
    $real = realpath($target);
    if ($real === false || !is_dir($real)) {
        throw new RuntimeException('La carpeta no existe');
    }
    $rootReal = realpath($root);
    if ($rootReal === false || strpos($real, $rootReal) !== 0) {
        throw new InvalidArgumentException('Ruta fuera del directorio permitido');
    }
    return $real;
}

function list_entries(string $root, string $rel): array
{
    $work = resolve_dir($root, $rel);
    $rel = normalize_rel($rel);
    $folders = [];
    $files = [];

    $entries = scandir($work) ?: [];
    natcasesort($entries);

    foreach ($entries as $name) {
        if (in_array($name, SKIP_NAMES, true)) {
            continue;
        }
        $full = $work . DIRECTORY_SEPARATOR . $name;
        $path = $rel === '' ? $name : ($rel . '/' . $name);

        if (is_dir($full)) {
            $folders[] = [
                'name' => $name,
                'type' => 'folder',
                'path' => $path,
                'protected' => false,
            ];
            continue;
        }

        if (!is_file($full)) {
            continue;
        }

        $ext = strtolower(pathinfo($name, PATHINFO_EXTENSION));
        $size = filesize($full);
        if ($size === false) {
            $size = 0;
        }

        $files[] = [
            'name' => $name,
            'type' => 'file',
            'path' => $path,
            'size' => $size,
            'size_label' => human_size($size),
            'ext' => $ext !== '' ? $ext : 'sin extensión',
            'protected' => false,
            'selected_default' => in_array($ext, ['log', 'tmp', 'cache', 'bak', 'old'], true),
        ];
    }

    usort($folders, static fn($a, $b) => strcasecmp($a['name'], $b['name']));
    usort($files, static fn($a, $b) => strcasecmp($a['name'], $b['name']));

    $total = array_sum(array_map(static fn($f) => $f['size'], $files));

    $crumbs = [['name' => 'Inicio', 'path' => '']];
    if ($rel !== '') {
        $built = [];
        foreach (explode('/', $rel) as $part) {
            $built[] = $part;
            $crumbs[] = ['name' => $part, 'path' => implode('/', $built)];
        }
    }

    $parent = null;
    if ($rel !== '') {
        $bits = explode('/', $rel);
        array_pop($bits);
        $parent = implode('/', $bits);
    }

    return [
        'root' => $root,
        'folder' => $work,
        'path' => $rel,
        'parent' => $parent,
        'breadcrumb' => $crumbs,
        'count' => count($files) + count($folders),
        'folder_count' => count($folders),
        'file_count' => count($files),
        'deletable_count' => count($files),
        'reclaimable_label' => human_size((int) $total),
        'folders' => $folders,
        'files' => $files,
        'agent' => true,
    ];
}

function safe_file(string $root, string $relFile): ?string
{
    try {
        $rel = normalize_rel($relFile);
    } catch (Throwable $e) {
        return null;
    }
    if ($rel === '') {
        return null;
    }
    if (in_array(basename($rel), SKIP_NAMES, true)) {
        return null;
    }

    $candidate = $root . DIRECTORY_SEPARATOR . str_replace('/', DIRECTORY_SEPARATOR, $rel);
    $real = realpath($candidate);
    $rootReal = realpath($root);
    if ($real === false || $rootReal === false || !is_file($real) || strpos($real, $rootReal) !== 0) {
        return null;
    }
    return $real;
}

function safe_dir(string $root, string $relDir): ?string
{
    try {
        $rel = normalize_rel($relDir);
    } catch (Throwable $e) {
        return null;
    }
    if ($rel === '') {
        return null;
    }
    if (in_array(basename($rel), SKIP_NAMES, true)) {
        return null;
    }

    $candidate = $root . DIRECTORY_SEPARATOR . str_replace('/', DIRECTORY_SEPARATOR, $rel);
    $real = realpath($candidate);
    $rootReal = realpath($root);
    if ($real === false || $rootReal === false || !is_dir($real) || strpos($real, $rootReal) !== 0) {
        return null;
    }
    return $real;
}

function dir_size(string $dir): int
{
    $total = 0;
    $iterator = new RecursiveIteratorIterator(
        new RecursiveDirectoryIterator($dir, FilesystemIterator::SKIP_DOTS)
    );
    foreach ($iterator as $file) {
        if ($file->isFile()) {
            $total += (int) $file->getSize();
        }
    }
    return $total;
}

function rrmdir(string $dir): bool
{
    if (!is_dir($dir)) {
        return false;
    }
    $items = scandir($dir) ?: [];
    foreach ($items as $item) {
        if ($item === '.' || $item === '..') {
            continue;
        }
        $path = $dir . DIRECTORY_SEPARATOR . $item;
        if (is_dir($path)) {
            if (!rrmdir($path)) {
                return false;
            }
        } elseif (!@unlink($path)) {
            return false;
        }
    }
    return @rmdir($dir);
}

function delete_files(string $root, array $names, string $currentPath): array
{
    $prefix = normalize_rel($currentPath);
    $deleted = [];
    $missing = [];
    $blocked = [];
    $freed = 0;

    foreach ($names as $raw) {
        $name = trim(str_replace('\\', '/', (string) $raw));
        if ($name === '') {
            continue;
        }

        $rel = str_contains($name, '/') ? $name : trim($prefix . '/' . $name, '/');

        try {
            $normalized = normalize_rel($rel);
        } catch (Throwable $e) {
            $missing[] = $name;
            continue;
        }

        if ($normalized === '') {
            $blocked[] = $name;
            continue;
        }

        $filePath = safe_file($root, $normalized);
        if ($filePath !== null) {
            $size = filesize($filePath) ?: 0;
            if (!@unlink($filePath)) {
                $missing[] = $name;
                continue;
            }
            $deleted[] = basename($filePath);
            $freed += $size;
            continue;
        }

        $dirPath = safe_dir($root, $normalized);
        if ($dirPath !== null) {
            $size = dir_size($dirPath);
            if (!rrmdir($dirPath)) {
                $missing[] = $name;
                continue;
            }
            $deleted[] = basename($dirPath) . '/';
            $freed += $size;
            continue;
        }

        $missing[] = $name;
    }

    if ($deleted && !$missing && !$blocked) {
        $message = 'Eliminados ' . count($deleted) . ' elemento(s): ' . implode(', ', $deleted);
    } elseif ($deleted) {
        $parts = ['Eliminados: ' . implode(', ', $deleted)];
        if ($missing) {
            $parts[] = 'No encontrados: ' . implode(', ', $missing);
        }
        if ($blocked) {
            $parts[] = 'Bloqueados: ' . implode(', ', $blocked);
        }
        $message = implode('. ', $parts);
    } elseif ($blocked && !$missing) {
        $message = 'No se pueden eliminar: ' . implode(', ', $blocked);
    } elseif ($missing) {
        $message = 'No se encontraron: ' . implode(', ', $missing);
    } else {
        $message = 'No había elementos para eliminar';
    }

    return [
        'deleted' => $deleted,
        'missing' => $missing,
        'blocked' => $blocked,
        'freed' => $freed,
        'freed_label' => human_size($freed),
        'message' => $message,
    ];
}
