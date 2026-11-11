# Python is installed in this immutable image, not by a build-time feature.
# Official image source: https://github.com/devcontainers/images/tree/main/src/python
FROM mcr.microsoft.com/devcontainers/python:1-3.12-bookworm@sha256:7876580dc67fd460fd962f004cbeb480027e9bbc0657096f1087db11f9eaff39
# The demos do not use Yarn. Its inherited package feed has an expired key and
# prevents the SSH feature's apt update; retain verification for active feeds.
RUN rm -f /etc/apt/sources.list.d/yarn.list
COPY --from=ghcr.io/astral-sh/uv:0.10.8 /uv /uvx /usr/local/bin/
RUN python3 -c 'import sys; assert sys.version_info[:2] == (3, 12), sys.version'
