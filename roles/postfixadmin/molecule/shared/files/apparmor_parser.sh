#!/bin/sh
# apparmor_parser of the test container: records the call and compiles the
# profile with the packaged parser, but does not load it into the kernel.
echo "$*" >> /root/molecule-apparmor-parser.log
exec /usr/sbin/apparmor_parser --skip-kernel-load --skip-cache "$@"
