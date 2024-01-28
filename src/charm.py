#!/usr/bin/env python3

#
# Copyright 2021 Canonical Ltd.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Cinder Ceph Operator Charm.

This charm provide Cinder <-> Linstor integration as part
of an OpenStack deployment
"""
import logging
import uuid
from typing import (
    Callable,
    List,
    Mapping,
    Optional,
)

import ops.charm
import ops_sunbeam.charm as charm
import ops_sunbeam.config_contexts as config_contexts
import ops_sunbeam.container_handlers as container_handlers
import ops_sunbeam.core as core
import ops_sunbeam.guard as sunbeam_guard
import ops_sunbeam.relation_handlers as relation_handlers
import ops_sunbeam.relation_handlers as sunbeam_rhandlers
import charms.cinder_k8s.v0.storage_backend as sunbeam_storage_backend
from ops.main import (
    main,
)
from ops.model import (
    Relation,
    SecretRotate,
)

logger = logging.getLogger(__name__)


class LinstorConfigurationContext(config_contexts.ConfigContext):
    """Configuration context to parse linstor parameters."""

    def context(self) -> dict:
        """Generate configuration information for linstor config."""
        config = self.charm.model.config.get
        linstor_uri = config("linstor-uris")
        
        return {
            "linstor_uri": linstor_uri,
        }


class CinderLinstorConfigurationContext(config_contexts.ConfigContext):
    """Configuration context for cinder parameters."""

    def context(self) -> dict:
        """Generate context information for cinder config."""
        config = self.charm.model.config.get

        backend_name = config("volume-backend-name") or self.charm.app.name
        volume_driver = "cinder.volume.drivers.linstordrv.Linstor%sDriver" % (
            config("linstor-driver").capitalize())

        # TODO:
        # Implement TLS
        return {
            "volume_backend_name": backend_name,
            "volume_driver": volume_driver,
        }


class StorageBackendProvidesHandler(sunbeam_rhandlers.RelationHandler):
    """Relation handler for storage-backend interface type."""

    def setup_event_handler(self):
        """Configure event handlers for an storage-backend relation."""
        logger.debug("Setting up Identity Service event handler")
        sb_svc = sunbeam_storage_backend.StorageBackendProvides(
            self.charm,
            self.relation_name,
        )
        self.framework.observe(sb_svc.on.api_ready, self._on_ready)
        return sb_svc

    def _on_ready(self, event) -> None:
        """Handles AMQP change events."""
        # Ready is only emitted when the interface considers
        # that the relation is complete (indicated by a password)
        self.callback_f(event)

    @property
    def ready(self) -> bool:
        """Check whether storage-backend interface is ready for use."""
        return self.interface.remote_ready()


class CinderVolumePebbleHandler(container_handlers.PebbleHandler):
    """Pebble handler for cinder-volume service."""

    def get_layer(self) -> dict:
        """cinder-volume service pebble layer.

        :returns: pebble layer configuration for cinder-volume service
        :rtype: dict
        """
        return {
            "summary": f"{self.service_name} layer",
            "description": "pebble config layer for cinder-volume service",
            "services": {
                self.service_name: {
                    "override": "replace",
                    "summary": self.service_name,
                    "command": f"{self.service_name} --use-syslog",
                    "user": "cinder",
                    "group": "cinder",
                },
            },
        }

    def start_service(self) -> None:
        """Start all services in associated container."""
        container = self.charm.unit.get_container(self.container_name)
        if not container:
            logger.debug(
                f"{self.container_name} container is not ready. "
                "Cannot start service."
            )
            return
        service = container.get_service(self.service_name)
        if service.is_running():
            container.stop(self.service_name)

        container.start(self.service_name)

    def init_service(self, context) -> None:
        """Write configs and start services."""
        self.write_config(context)
        self.start_service()


class CinderLinstorOperatorCharm(charm.OSBaseOperatorCharmK8S):
    """Cinder/Linstor Operator charm."""

    # NOTE: service_name == container_name
    service_name = "cinder-volume"

    service_user = "cinder"
    service_group = "cinder"

    cinder_conf = "/etc/cinder/cinder.conf"

    mandatory_relations = {
        "database",
        "amqp",
    }

    def __init__(self, framework):
        super().__init__(framework)
        self._state.set_default(api_ready=False)

    def get_relation_handlers(self) -> List[relation_handlers.RelationHandler]:
        """Relation handlers for the service."""
        handlers = super().get_relation_handlers()
        self.sb_svc = StorageBackendProvidesHandler(
            self,
            "storage-backend",
            self.api_ready,
            "storage-backend" in self.mandatory_relations,
        )
        handlers.append(self.sb_svc)
        return handlers

    def get_pebble_handlers(self) -> List[container_handlers.PebbleHandler]:
        """Pebble handlers for the operator."""
        return [
            CinderVolumePebbleHandler(
                self,
                self.service_name,
                self.service_name,
                self.container_configs,
                self.template_dir,
                self.configure_charm,
            )
        ]

    def api_ready(self, event) -> None:
        """Event handler for bootstrap of service when api services are ready."""
        self._state.api_ready = True
        self.configure_charm(event)
        if self.bootstrapped():
            for handler in self.pebble_handlers:
                handler.start_service()

    @property
    def config_contexts(self) -> List[config_contexts.ConfigContext]:
        """Configuration contexts for the operator."""
        contexts = super().config_contexts
        contexts.append(LinstorConfigurationContext(self, "linstor_config"))
        contexts.append(CinderLinstorConfigurationContext(self, "cinder_linstor"))
        return contexts

    @property
    def container_configs(self) -> List[core.ContainerConfigFile]:
        """Container configurations for the operator."""
        _cconfigs = super().container_configs
        _cconfigs.extend(
            [
                core.ContainerConfigFile(
                    self.cinder_conf,
                    "root",
                    self.service_group,
                    0o640,
                ),
            ]
        )
        return _cconfigs

    @property
    def databases(self) -> Mapping[str, str]:
        """Provide database name for cinder services."""
        return {"database": "cinder"}

    def configure_app_leader(self, event: ops.framework.EventBase):
        """Run global app setup.

        These are tasks that should only be run once per application and only
        the leader runs them.
        """
        pass

    def can_service_requests(self) -> bool:
        """Check if unit can process client requests."""
        if self.bootstrapped() and self.unit.is_leader():
            logger.debug("Can service client requests")
            return True
        else:
            logger.debug(
                "Cannot service client requests. "
                "Bootstrapped: {} Leader {}".format(
                    self.bootstrapped(), self.unit.is_leader()
                )
            )
            return False


if __name__ == "__main__":
    main(CinderLinstorOperatorCharm)
