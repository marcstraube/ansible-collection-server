<?php

// Managed by Ansible (marcstraube.server.postfixadmin).
//
// Runs the code of a PostfixAdmin installation for the role: the schema
// status and upgrade (public/upgrade.php, the code setup.php runs), the
// accounts (the *Handler classes postfixadmin-cli uses) and the SOGo view.
// The request comes as JSON on stdin, so passwords never appear in the
// process list; the result is printed as JSON on stdout.
//
// Usage: php postfixadmin-ansible.php <PostfixAdmin directory> < request.json
//
// Requests:
//   {"action": "status"}
//   {"action": "upgrade"}
//   {"action": "accounts", "type": "mailbox", "check": false, "entries": [
//      {"id": "...", "state": "present", "mode": "managed",
//       "values": {...}, "password": "..."}]}
//   {"action": "sogo_view", "name": "sogo_users", "state": "present",
//    "check": false}

if (PHP_SAPI !== 'cli') {
    exit(1);
}

define('POSTFIXADMIN_CLI', 1);

// PostfixAdmin passes failed queries with their parameters (password
// hashes among them) to error_log(), which writes to stderr on the command
// line whatever log_errors says, and stderr ends up in the Ansible output.
// The helper reports its errors in its own JSON result instead. PHP
// warnings go to stderr so that stdout carries the JSON result only, and
// stack traces leave out the arguments (passwords).
ini_set('log_errors', '0');
ini_set('error_log', '/dev/null');
ini_set('display_errors', 'stderr');
ini_set('zend.exception_ignore_args', '1');

$pfa_ansible_root = rtrim($argv[1] ?? '', '/');
if ($pfa_ansible_root === '' || !is_file($pfa_ansible_root . '/common.php')) {
    fwrite(STDERR, "PostfixAdmin not found in '$pfa_ansible_root'\n");
    exit(2);
}

$pfa_ansible_request = json_decode((string) stream_get_contents(STDIN), true);
if (!is_array($pfa_ansible_request) || !isset($pfa_ansible_request['action'])) {
    fwrite(STDERR, "Invalid request: expected a JSON object with an action\n");
    exit(2);
}

/**
 * Output of PostfixAdmin itself (upgrade progress, the message of a die())
 * collected so far, without HTML.
 */
function pfa_ansible_output(): string
{
    $output = '';
    while (ob_get_level() > 0) {
        $output = (string) ob_get_clean() . $output;
    }
    return trim(strip_tags($output));
}

/**
 * Prints the result as JSON and ends the script; output of PostfixAdmin
 * itself is passed on as 'output'.
 */
function pfa_ansible_finish(array $result, int $code = 0): void
{
    $GLOBALS['pfa_ansible_finished'] = true;
    $output = pfa_ansible_output();
    if ($output !== '') {
        $result['output'] = $output;
    }
    echo json_encode($result, JSON_UNESCAPED_SLASHES | JSON_UNESCAPED_UNICODE), "\n";
    exit($code);
}

function pfa_ansible_fail(string $message, array $result = []): void
{
    $result['failed'] = true;
    $result['msg'] = $message;
    pfa_ansible_finish($result, 1);
}

/**
 * PostfixAdmin ends the script with die() / exit on some errors (a missing
 * or invalid configuration, an outdated schema), which exits with status 0.
 * Every regular end goes through pfa_ansible_finish(); any other end is a
 * failure and exits non-zero with what PostfixAdmin printed.
 */
$pfa_ansible_finished = false;
register_shutdown_function(function (): void {
    if ($GLOBALS['pfa_ansible_finished']) {
        return;
    }
    $message = pfa_ansible_output();
    $error = error_get_last();
    if ($message === '' && $error !== null) {
        // The first line only: the stack trace follows on the next lines
        $message = strtok((string) $error['message'], "\n");
    }
    echo json_encode([
        'failed' => true,
        'msg' => 'PostfixAdmin ended the helper before it completed'
            . ($message !== '' ? ': ' . $message : ''),
    ], JSON_UNESCAPED_SLASHES | JSON_UNESCAPED_UNICODE), "\n";
    exit(1);
});

/**
 * Schema version recorded in the config table; 0 while the table or the
 * row is missing (empty database).
 */
function pfa_ansible_db_version(): int
{
    try {
        $row = db_query_one("SELECT value FROM " . table_by_key('config') . " WHERE name = 'version'");
    } catch (\Throwable $e) {
        return 0;
    }
    return isset($row['value']) ? (int) $row['value'] : 0;
}

/**
 * Schema version the release requires: $min_db_version of functions.inc.php,
 * the version PostfixAdmin itself checks before it works with the database
 * (check_db_version()). Composer loads functions.inc.php from a function,
 * so the variable is not a global and is read from the file. A release
 * without it cannot be checked, so the helper fails instead of reporting
 * a schema as up to date.
 */
function pfa_ansible_target_version(string $root): int
{
    $target = 0;
    $source = (string) @file_get_contents($root . '/functions.inc.php');
    if (preg_match('/^\$min_db_version\s*=\s*(\d+)\s*;/m', $source, $match)) {
        $target = (int) $match[1];
    }
    if ($target <= 0) {
        pfa_ansible_fail('The release defines no schema version ($min_db_version in functions.inc.php)');
    }
    return $target;
}

/**
 * Attributes that only apply when an entry is created (the default aliases
 * of a domain, the welcome mail of a mailbox).
 */
const PFA_ANSIBLE_CREATE_ONLY = ['default_aliases', 'welcome_mail'];

/**
 * Converts the booleans of the request to 1 / 0, the values the handlers
 * validate (postfixadmin-cli converts y / n the same way).
 */
function pfa_ansible_normalize(array $struct, array $values): array
{
    foreach ($values as $key => $value) {
        if (isset($struct[$key]) && $struct[$key]['type'] === 'bool') {
            $values[$key] = pfa_ansible_bool($value) ? 1 : 0;
        }
    }
    return $values;
}

function pfa_ansible_bool($value): bool
{
    if (is_bool($value)) {
        return $value;
    }
    return in_array(strtolower(trim((string) $value)), ['1', 't', 'true', 'y', 'yes', 'on'], true);
}

/**
 * Compares a stored value with the requested one by the field type of the
 * handler.
 */
function pfa_ansible_equal(string $type, $current, $wanted): bool
{
    switch ($type) {
        case 'bool':
            return pfa_ansible_bool($current) === pfa_ansible_bool($wanted);
        case 'int':
        case 'num':
            return (string) (int) $current === (string) (int) $wanted;
        case 'txtl':
        case 'list':
            $current = is_array($current) ? $current : array_filter(explode(',', (string) $current), 'strlen');
            $wanted = is_array($wanted) ? $wanted : [$wanted];
            $current = array_map('strtolower', array_map('trim', array_map('strval', $current)));
            $wanted = array_map('strtolower', array_map('trim', array_map('strval', $wanted)));
            sort($current);
            sort($wanted);
            return array_values(array_unique($current)) === array_values(array_unique($wanted));
        default:
            return (string) $current === (string) $wanted;
    }
}

/**
 * Checks a password against the stored hash with PostfixAdmin's own
 * pacrypt(), as the login does: 'same', 'differs', or 'rehash' when the
 * password matches a hash of another scheme than $CONF['encrypt'].
 */
function pfa_ansible_password_state(string $table, string $id, string $password): string
{
    $row = db_query_one(
        "SELECT password FROM " . table_by_key($table) . " WHERE username = :username",
        ['username' => $id]
    );
    $stored = (string) ($row['password'] ?? '');
    if ($stored === '') {
        return 'differs';
    }
    try {
        $hashed = pacrypt($password, $stored);
    } catch (\Throwable $e) {
        return 'differs';
    }
    if (!hash_equals($stored, (string) $hashed)) {
        return 'differs';
    }
    $prefix = '{' . strtoupper(Config::read_string('encrypt')) . '}';
    return strncmp($stored, $prefix, strlen($prefix)) === 0 ? 'same' : 'rehash';
}

/**
 * A superadmin is recorded with the pseudo domain 'ALL' in domain_admins,
 * which references the domain table; setup.php inserts that row before it
 * creates the first superadmin, so the role does the same.
 */
function pfa_ansible_ensure_all_domain(): void
{
    $table = table_by_key('domain');
    if (empty(db_query_all("SELECT domain FROM $table WHERE domain = 'ALL'"))) {
        db_insert('domain', ['domain' => 'ALL', 'description' => '', 'transport' => '']);
    }
}

function pfa_ansible_errors($handler): string
{
    $messages = [];
    foreach ((array) $handler->errormsg as $field => $message) {
        $messages[] = is_int($field) ? (string) $message : "$field: $message";
    }
    return implode('; ', $messages);
}

/**
 * Applies the entries of one account type with the *Handler class that
 * postfixadmin-cli uses for it (init, set, save, delete).
 */
function pfa_ansible_accounts(array $request): array
{
    $types = [
        'admin' => ['class' => 'AdminHandler', 'password_table' => 'admin'],
        'domain' => ['class' => 'DomainHandler', 'password_table' => ''],
        'mailbox' => ['class' => 'MailboxHandler', 'password_table' => 'mailbox'],
        'alias' => ['class' => 'AliasHandler', 'password_table' => ''],
        'alias_domain' => ['class' => 'PfaAnsibleAliasdomainHandler', 'password_table' => ''],
    ];
    $type = (string) ($request['type'] ?? '');
    if (!isset($types[$type])) {
        pfa_ansible_fail("Unknown account type '$type'");
    }
    $class = $types[$type]['class'];
    $password_table = $types[$type]['password_table'];
    $check = !empty($request['check']);

    $results = [];
    $changed = false;
    foreach ((array) ($request['entries'] ?? []) as $entry) {
        $id = strtolower(trim((string) ($entry['id'] ?? '')));
        $state = (string) ($entry['state'] ?? 'present');
        $mode = (string) ($entry['mode'] ?? 'managed');
        $values = (array) ($entry['values'] ?? []);
        $password = isset($entry['password']) ? (string) $entry['password'] : null;

        // PostfixAdmin throws for some invalid entries (e.g. a mailbox of an
        // unknown domain); the message names the entry like a handler error.
        try {
            if ($type === 'admin' && $state === 'present' && !$check
                && pfa_ansible_bool($values['superadmin'] ?? false)) {
                pfa_ansible_ensure_all_domain();
            }

            $handler = new $class(0);
            $exists = $handler->init($id);
            $values = pfa_ansible_normalize($handler->getStruct(), $values);

            if ($state === 'absent') {
                $action = $exists ? 'deleted' : 'unchanged';
                if ($exists && !$check && !$handler->delete()) {
                    pfa_ansible_fail("$type $id: " . pfa_ansible_errors($handler), ['results' => $results]);
                }
            } elseif (!$exists && $check) {
                // A check run cannot validate a new entry that depends on
                // another new one (a mailbox of a domain the run would create).
                $action = 'created';
            } elseif (!$exists) {
                $action = 'created';
                $handler = new $class(1);
                if (!$handler->init($id)) {
                    pfa_ansible_fail("$type $id: " . pfa_ansible_errors($handler), ['results' => $results]);
                }
                if ($password !== null) {
                    $values['password'] = $password;
                    $values['password2'] = $password;
                }
                if ($type === 'mailbox') {
                    // The role creates mailboxes without sending a welcome mail.
                    $values['welcome_mail'] = 0;
                }
                if (!$handler->set($values) || !$handler->save()) {
                    pfa_ansible_fail("$type $id: " . pfa_ansible_errors($handler), ['results' => $results]);
                }
            } elseif ($mode !== 'managed') {
                $action = 'unchanged';
            } else {
                $struct = $handler->getStruct();
                $current = $handler->result();
                $update = [];
                $fields = [];
                foreach ($values as $key => $wanted) {
                    if (in_array($key, PFA_ANSIBLE_CREATE_ONLY, true)) {
                        continue;
                    }
                    if (!isset($struct[$key]) || !$struct[$key]['editable']) {
                        pfa_ansible_fail(
                            "$type $id: '$key' cannot be changed with the current PostfixAdmin configuration",
                            ['results' => $results]
                        );
                    }
                    if (!pfa_ansible_equal($struct[$key]['type'], $current[$key] ?? null, $wanted)) {
                        $update[$key] = $wanted;
                        $fields[] = $key;
                    }
                }
                // With $CONF['mailbox_postpassword_script'] the handler does not
                // let the password of an existing mailbox change (it is not
                // editable and set() drops it), so it is only set on creation;
                // comparing it would report a change on every run.
                if ($password !== null && $password_table !== ''
                    && !empty($struct['password']['editable'])
                    && pfa_ansible_password_state($password_table, $id, $password) !== 'same') {
                    $update['password'] = $password;
                    $update['password2'] = $password;
                    $fields[] = 'password';
                }
                $action = empty($update) ? 'unchanged' : 'updated';
                if (!empty($update)) {
                    $handler = new $class(0);
                    $handler->init($id);
                    if (!$handler->set($update) || (!$check && !$handler->save())) {
                        pfa_ansible_fail("$type $id: " . pfa_ansible_errors($handler), ['results' => $results]);
                    }
                }
            }
        } catch (\Throwable $e) {
            pfa_ansible_fail("$type $id: " . $e->getMessage(), ['results' => $results]);
        }

        $result = ['id' => $id, 'action' => $action];
        if (!empty($fields)) {
            $result['fields'] = $fields;
        }
        $results[] = $result;
        $changed = $changed || $action !== 'unchanged';
    }

    return ['changed' => $changed, 'results' => $results];
}

/**
 * Columns of a table or view in the PostfixAdmin database, in order; an
 * empty list when it does not exist.
 */
function pfa_ansible_columns(string $name): array
{
    if (db_pgsql()) {
        $sql = "SELECT column_name FROM information_schema.columns
                WHERE table_schema = current_schema() AND table_name = :name
                ORDER BY ordinal_position";
    } else {
        $sql = "SELECT column_name FROM information_schema.columns
                WHERE table_schema = DATABASE() AND table_name = :name
                ORDER BY ordinal_position";
    }
    $rows = db_query_all($sql, ['name' => $name]);
    return array_map(function ($row) {
        return strtolower((string) reset($row));
    }, $rows);
}

/**
 * The view of the SOGo user source: one row per active mailbox of an
 * active domain with the columns SOGo's SQL source expects.
 */
function pfa_ansible_sogo_view(array $request): array
{
    $name = (string) ($request['name'] ?? '');
    if (!preg_match('/^[a-z_][a-z0-9_]*$/', $name)) {
        pfa_ansible_fail("Invalid view name '$name'");
    }
    $check = !empty($request['check']);
    $state = (string) ($request['state'] ?? 'present');
    $columns = ['c_uid', 'c_name', 'c_password', 'c_cn', 'mail', 'domain'];
    $existing = pfa_ansible_columns($name);
    $quoted = db_mysql() ? "`$name`" : $name;

    if ($state === 'absent') {
        // Only the view of the role: another object of that name stays.
        if ($existing !== $columns) {
            return ['changed' => false];
        }
        if (!$check) {
            db_execute("DROP VIEW $quoted", [], true);
        }
        return ['changed' => true];
    }

    if ($existing === $columns) {
        return ['changed' => false];
    }
    if (!$check) {
        if (!empty($existing)) {
            db_execute("DROP VIEW $quoted", [], true);
        }
        $mailbox = table_by_key('mailbox');
        $domain = table_by_key('domain');
        db_execute(
            "CREATE VIEW $quoted AS
             SELECT m.username AS c_uid, m.username AS c_name, m.password AS c_password,
                    m.name AS c_cn, m.username AS mail, m.domain AS domain
             FROM $mailbox m JOIN $domain d ON d.domain = m.domain
             WHERE m.active AND d.active",
            [],
            true
        );
    }
    return ['changed' => true];
}

chdir($pfa_ansible_root);
ob_start();
require_once $pfa_ansible_root . '/common.php';

/**
 * AliasdomainHandler::initStruct() removes the only domain that could
 * still become an alias domain from the target options: a hint for the
 * create form, so that the form does not offer that domain as its own
 * target. When an existing alias domain gets a new target, the hint also
 * rejects a valid target (with example.org -> example.com and example.net
 * as the only other domain, example.net is refused). For an existing
 * alias domain the options are therefore every domain that is not an
 * alias domain itself, which keeps PostfixAdmin's rules: no chained alias
 * domains, and _validate_target_domain() still refuses the alias domain
 * as its own target. Declared after common.php, whose autoloader provides
 * the parent class, and only when it does (a release without the class
 * still gets the status and upgrade actions).
 */
if (class_exists('AliasdomainHandler')) {
    class PfaAnsibleAliasdomainHandler extends AliasdomainHandler
    {
        protected function initStruct()
        {
            parent::initStruct();
            if ($this->new) {
                return;
            }
            foreach ($this->allowed_domains as $domain) {
                if (!isset($this->result[$domain])) {
                    $this->struct['target_domain']['options'][$domain] = $domain;
                }
            }
        }
    }
}

try {
    db_connect();
} catch (\Throwable $e) {
    pfa_ansible_fail('Cannot connect to the database: ' . $e->getMessage());
}

switch ($pfa_ansible_request['action']) {
    case 'status':
        pfa_ansible_finish([
            'changed' => false,
            'db_version' => pfa_ansible_db_version(),
            'target_version' => pfa_ansible_target_version($pfa_ansible_root),
            'release' => (string) Config::read_string('version'),
        ]);
        break;

    case 'upgrade':
        // upgrade.php works on the global $CONF, so it is included at the top
        // level of this script, not from a function.
        $pfa_ansible_before = pfa_ansible_db_version();
        try {
            $pfa_ansible_upgraded = require $pfa_ansible_root . '/public/upgrade.php';
        } catch (\Throwable $e) {
            pfa_ansible_fail('Schema upgrade failed: ' . $e->getMessage(), ['db_version' => pfa_ansible_db_version()]);
        }
        $pfa_ansible_after = pfa_ansible_db_version();
        if ($pfa_ansible_upgraded !== true) {
            pfa_ansible_fail('Schema upgrade failed', ['db_version' => $pfa_ansible_after]);
        }
        pfa_ansible_finish([
            'changed' => $pfa_ansible_after !== $pfa_ansible_before,
            'db_version_before' => $pfa_ansible_before,
            'db_version' => $pfa_ansible_after,
        ]);
        break;

    case 'accounts':
        try {
            pfa_ansible_finish(pfa_ansible_accounts($pfa_ansible_request));
        } catch (\Throwable $e) {
            pfa_ansible_fail($e->getMessage());
        }
        break;

    case 'sogo_view':
        try {
            pfa_ansible_finish(pfa_ansible_sogo_view($pfa_ansible_request));
        } catch (\Throwable $e) {
            pfa_ansible_fail($e->getMessage());
        }
        break;

    default:
        pfa_ansible_fail('Unknown action ' . json_encode($pfa_ansible_request['action']));
}
