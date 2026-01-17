FROM ubuntu:22.04

ENV DEBIAN_FRONTEND=noninteractive

# Базовые инструменты для сборки ядра, работы с .deb и создания образа
RUN apt-get update && \
    apt-get install -y \
      build-essential libncurses-dev bison flex libssl-dev bc git gpgv2 \
      wget ca-certificates curl binutils tar xz-utils zstd \
      util-linux dosfstools e2fsprogs kmod udev \
      qemu-system-aarch64 open-iscsi openvswitch-switch python3-openvswitch \
      python3 python3-pip python3-venv python3-setuptools && \
    apt-get clean && rm -rf /var/lib/apt/lists/*

WORKDIR /workspace

# По умолчанию оставляем интерактивную оболочку; сборку вызывайте через docker run
CMD ["/bin/bash"]
