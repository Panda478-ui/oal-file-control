<?php
/**
 * OAL File Control — agente remoto
 *
 * Colócalo en la carpeta del sitio (ej. /lab_sys/oal_agent.php).
 * Luego conecta desde https://oal-file-control.onrender.com
 * con la URL del sitio o de este agente.
 *
 * Seguridad: cambia OAL_AGENT_TOKEN antes de usar en producción.
 */

declare(strict_types=1);

header('Access-Control-Allow-Origin: *');
header('Access-Control-Allow-Methods: GET, POST, OPTIONS');
header('Access-Control-Allow-Headers: Content-Type, X-OAL-Token, ngrok-skip-browser-warning');

if (($_SERVER['REQUEST_METHOD'] ?? 'GET') === 'OPTIONS') {
    http_response_code(204);
    exit;
}

// Cambia este token si expones el agente públicamente
const OAL_AGENT_TOKEN = 'oal-lab-clean';

const PROTECTED_NAMES = [
    'oal_agent.php',
    'config.php',
    'config.local.php',
    'config.school.php',
    'composer.json',
    'composer.lock',
    '.htaccess',
    '.env',
];

const SKIP_NAMES = ['.', '..', '.git', 'vendor'];

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

if (!hash_equals(OAL_AGENT_TOKEN, (string) $token)) {
    json_out(401, ['error' => 'Token inválido. Usa token=oal-lab-clean']);
}

$action = $_GET['action'] ?? ($body['action'] ?? 'files');
$method = $_SERVER['REQUEST_METHOD'] ?? 'GET';

if ($action === 'ping') {
    json_out(200, [
        'ok' => true,
        'agent' => 'oal_agent',
        'version' => '1.0',
        'root' => $root,
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

        $protected = in_array($name, PROTECTED_NAMES, true) && $rel === '';
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
            'protected' => $protected,
            'selected_default' => !$protected && in_array($ext, ['log', 'tmp', 'cache', 'bak', 'old'], true),
        ];
    }

    // Carpetas primero visualmente (ya vienen ordenadas por nombre; UI también las separa)
    usort($folders, static fn($a, $b) => strcasecmp($a['name'], $b['name']));
    usort($files, static fn($a, $b) => strcasecmp($a['name'], $b['name']));

    $reclaimable = array_values(array_filter($files, static fn($f) => !$f['protected']));
    $total = array_sum(array_map(static fn($f) => $f['size'], $reclaimable));

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
        'deletable_count' => count($reclaimable),
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

    $name = basename($rel);
    $parent = str_replace('\\', '/', dirname($rel));
    if ($parent === '.') {
        $parent = '';
    }

    if (in_array($name, PROTECTED_NAMES, true) && $parent === '') {
        return null;
    }
    if (in_array($name, SKIP_NAMES, true)) {
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
            $pure = basename(normalize_rel($rel));
        } catch (Throwable $e) {
            $missing[] = $name;
            continue;
        }

        if (in_array($pure, PROTECTED_NAMES, true) && !str_contains(normalize_rel($rel), '/')) {
            $blocked[] = $name;
            continue;
        }

        $path = safe_file($root, $rel);
        if ($path === null) {
            $missing[] = $name;
            continue;
        }

        $size = filesize($path) ?: 0;
        if (!@unlink($path)) {
            $missing[] = $name;
            continue;
        }
        $deleted[] = basename($path);
        $freed += $size;
    }

    if ($deleted && !$missing && !$blocked) {
        $message = 'Eliminados ' . count($deleted) . ' archivo(s): ' . implode(', ', $deleted);
    } elseif ($deleted) {
        $parts = ['Eliminados: ' . implode(', ', $deleted)];
        if ($missing) {
            $parts[] = 'No encontrados: ' . implode(', ', $missing);
        }
        if ($blocked) {
            $parts[] = 'Protegidos: ' . implode(', ', $blocked);
        }
        $message = implode('. ', $parts);
    } elseif ($blocked && !$missing) {
        $message = 'No se pueden eliminar (protegidos): ' . implode(', ', $blocked);
    } elseif ($missing) {
        $message = 'No se encontraron: ' . implode(', ', $missing);
    } else {
        $message = 'No había archivos para eliminar';
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
