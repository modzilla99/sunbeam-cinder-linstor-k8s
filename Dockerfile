FROM ghcr.io/canonical/cinder-consolidated:2023.2 as base

FROM base as build
RUN --mount=type=tmpfs,dst=/var/lib/apt/lists \
    --mount=type=tmpfs,dst=/var/cache/apt \
    --mount=type=tmpfs,dst=/var/log \
    apt update &&\
    apt install -y python3-pip
# Install required python library 
RUN pip3 install python-linstor
# Install linstordriver v2.0.0
ADD --chmod=0644 https://github.com/LINBIT/openstack-cinder/raw/7c3b4f88d9b02fd6e82408dc638c8bc8518425f5/cinder/volume/drivers/linstordrv.py \
    /tmp/linstordrv.py
# Patch Linstordrv to skip checking wheter host is part of linstor cluster
RUN sed -i  's/.*nodes.nodes.*/        if False:/' /tmp/linstordrv.py


FROM base
COPY --from=build /tmp/linstordrv.py /usr/lib/python3/dist-packages/cinder/volume/drivers/linstordrv.py
COPY --from=build /usr/local/lib/python3.10/dist-packages/linstor /usr/lib/python3/dist-packages/linstor