<?php

// Molecule verify helper, independent of the role's helper:
//   php query.php sql <PostfixAdmin directory> <query>
//     runs the query through the database connection of PostfixAdmin and
//     prints the rows as JSON
//   php query.php exec <PostfixAdmin directory> <statement>
//     runs a statement that returns no rows and prints the affected rows
//   php query.php password <hash> < password
//     prints whether the password matches the hash (scheme prefix removed)

if ($argv[1] === 'password') {
    $hash = preg_replace('/^\{[A-Z0-9.-]+\}/', '', $argv[2]);
    echo json_encode(password_verify(rtrim((string) stream_get_contents(STDIN), "\n"), $hash)), "\n";
    exit(0);
}

define('POSTFIXADMIN_CLI', 1);
chdir($argv[2]);
ob_start();
require 'common.php';
ob_end_clean();
if ($argv[1] === 'exec') {
    echo json_encode(db_execute($argv[3], [], true)), "\n";
} else {
    echo json_encode(db_query_all($argv[3])), "\n";
}
