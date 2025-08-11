# Prometheus Rules Layout

In this repository, Prometheus alert/record rules are typically managed under:

- `collections/prometheus` (provisioned into the Prometheus container)

The operational directory `maelstrom_mgmt/prometheus/rules` may be empty on hosts where rules are not staged locally. Validation should confirm rule groups via the Prometheus API:

- `GET http://localhost:9090/api/v1/rules`

If desired for operator convenience, a symlink can be created on the host from `maelstrom_mgmt/prometheus/rules` to `collections/prometheus`, but this is not required for Prometheus to load rules.

