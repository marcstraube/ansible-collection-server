<?php
// Managed by Ansible (marcstraube.server.roundcube).
//
// Reads the schema state of the Roundcube database with the code of a
// release: the tables, the schema version of the 'system' table and the
// newest schema version the release ships for the database type. The
// release reads the connection from its config/config.inc.php.
//
// Usage: php roundcube-schema.php <release directory>
// Prints one JSON object.

if (PHP_SAPI !== 'cli' || $argc !== 2) {
    fwrite(STDERR, "Usage: php roundcube-schema.php <release directory>\n");
    exit(2);
}

$release = realpath($argv[1]);
if ($release === false || !is_file($release . '/program/include/clisetup.php')) {
    fwrite(STDERR, "{$argv[1]} is not a Roundcube release\n");
    exit(2);
}

define('INSTALL_PATH', $release . '/');

require_once INSTALL_PATH . 'program/include/clisetup.php';

// Exits with the error when the database is not reachable
$db = rcmail_utils::db();

// With db_prefix only the tables of that prefix belong to Roundcube
$prefix = (string) rcmail::get_instance()->config->get('db_prefix');
$tables = array_values(array_filter(
    (array) $db->list_tables(),
    static fn ($table) => $prefix === '' || strpos($table, $prefix) === 0
));
$system = in_array($db->table_name('system'), $tables, true);
$version = $system ? (int) rcmail_utils::db_version('roundcube') : 0;

// The updates of the release; <type>.initial.sql creates the newest one
$target = 0;
foreach ((array) glob(INSTALL_PATH . 'SQL/' . $db->db_provider . '/*.sql') as $file) {
    if (preg_match('/^([0-9]+)\.sql$/', basename($file), $match)) {
        $target = max($target, (int) $match[1]);
    }
}

echo json_encode([
    'provider' => $db->db_provider,
    'tables' => count($tables),
    'system' => $system,
    'version' => $version,
    'target' => $target,
    'release' => RCMAIL_VERSION,
]), "\n";
