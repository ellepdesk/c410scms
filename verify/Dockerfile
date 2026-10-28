# Copyright (C) 2026 Pelle van der Heide
# SPDX-License-Identifier: GPL-2.0-or-later
#
# Reference environment: Samsung's own driver next to this project, for bit-exact comparison.
# Samsung's packages are downloaded from SULDR while the image is built; none of their files
# are part of this repository. Build context is the repository root (see verify/run).
FROM --platform=linux/amd64 debian:bookworm-slim

RUN apt-get update \
 && apt-get install -y --no-install-recommends \
      ca-certificates curl binutils xz-utils gcc libc6-dev make \
      libcups2 libcupsimage2 printer-driver-foo2zjs python3 python3-numpy \
 && rm -rf /var/lib/apt/lists/*

ARG SULDR=https://www.bchemnet.com/suldr/pool/debian/extra/su
ARG DRIVER_DEB=suld-driver2_1.00.39-2_amd64.deb
ARG DRIVER_SHA256=4de465c27bc65a0ac8a62f66b1ef5a15d8c2655983555d018311b4b7ca58b27a
ARG PPD_DEB=suld-ppd-4_1.00.39-2_all.deb
ARG PPD_SHA256=0ee498bb67d2ad2c65c11dd3824ed5aee9fac3f25c43536d422e383b43d14d4b

RUN set -e; mkdir -p /tmp/suld /opt/suld; cd /tmp/suld; \
    curl -fsSLO "$SULDR/$DRIVER_DEB"; curl -fsSLO "$SULDR/$PPD_DEB"; \
    echo "$DRIVER_SHA256  $DRIVER_DEB" | sha256sum -c -; \
    echo "$PPD_SHA256  $PPD_DEB" | sha256sum -c -; \
    for deb in "$DRIVER_DEB" "$PPD_DEB"; do ar x "$deb" data.tar.xz && tar xJf data.tar.xz -C /opt/suld && rm data.tar.xz; done; \
    install -D -m 755 /opt/suld/usr/lib/cups/filter/rastertospl /usr/lib/cups/filter/rastertospl; \
    install -D -m 644 /opt/suld/usr/lib/libscmssc.so /opt/smfp-common/printer/lib/libscmssc.so; \
    mkdir -p /usr/share/cups/model/uld-samsung && cp -r /opt/suld/usr/share/ppd/suld/cms /usr/share/cups/model/uld-samsung/; \
    rm -rf /tmp/suld

COPY . /src
WORKDIR /src
RUN make -s c410scms-filter

ENTRYPOINT ["python3", "-I", "/src/verify/harness.py"]
