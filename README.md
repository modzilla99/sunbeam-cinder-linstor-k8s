# cinder-ceph-k8s

## Description

The cinder-linstor-k8s is an operator to manage the Cinder service
integration with Linstor SDS storage backend on a Kubernetes based
environment. It is based on the cinder-ceph-k8s operator.

## Usage

### Deployment

Example config:

    $ cat linstor.yml 
    cinder-linstor-k8s:
      linstor-uris: linstor://192.168.122.111
      linstor-driver: drbd


cinder-linstor-k8s is deployed using below command:

    juju deploy cinder-linstor-k8s cinder-linstor --trust --config linstor.yml

Now connect the cinder-ceph application to database and messaging services:

    juju relate mysql:database cinder-linstor:database
    juju relate rabbitmq:amqp cinder-linstor:amqp
    juju relate cinder:storage-backend cinder-linstor-k8s:storage-backend

### Configuration

This section covers common and/or important configuration options. See file
`config.yaml` for the full list of options, along with their descriptions and
default values. See the [Juju documentation][juju-docs-config-apps] for details
on configuring applications.

### Actions

This section covers Juju [actions][juju-docs-actions] supported by the charm.
Actions allow specific operations to be performed on a per-unit basis. To
display action descriptions run `juju actions cinderceph`. If the charm is not
deployed then see file `actions.yaml`.

## Relations

cinder-ceph-k8s requires the following relations:

`amqp`: To connect to RabbitMQ
`database`: To connect to MySQL
`storage-backend`: To connect to Cinder

## OCI Images

The charm by default uses `docker.io/modzilla/cinder-consolidated-linstor:2023.2`

## Contributing

Please see the [Juju SDK docs](https://juju.is/docs/sdk) for guidelines
on enhancements to this charm following best practice guidelines, and
[CONTRIBUTING.md](contributors-guide) for developer guidance.

## Bugs

Please report bugs on [Launchpad][lp-bugs-charm-cinder-ceph-k8s].

<!-- LINKS -->

[contributors-guide]: https://opendev.org/openstack/charm-cinder-ceph-k8s/src/branch/main/CONTRIBUTING.md
[juju-docs-actions]: https://jaas.ai/docs/actions
[juju-docs-config-apps]: https://juju.is/docs/configuring-applications
[lp-bugs-charm-cinder-ceph-k8s]: https://bugs.launchpad.net/charm-cinder-ceph-k8s/+filebug
