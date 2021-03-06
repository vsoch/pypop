# vim: ts=4 sw=4 noet

BootStrap: yum
OSVersion: 25
MirrorURL: https://mirrors.kernel.org/fedora/releases/%{OSVERSION}/Everything/x86_64/os/
GPG: https://getfedora.org/static/FDB19C98.txt
Include: swig gcc.x86_64 gsl-devel.x86_64 python-devel.x86_64 python-numeric python-libxml2 libxslt-python redhat-rpm-config yum rpm.x86_64 vim

%setup
	# Copy all files into a directory in the container
	# (Make sure to exclude our Singularity image file)
	# (We use -rlptD instead of -a because owner & group can be ignored.)
	mkdir ${SINGULARITY_ROOTFS}/pypop-source
	rsync -rlptD --exclude '*.img' . ${SINGULARITY_ROOTFS}/pypop-source/

%post
	# Inside the container, build pypop
	# (to be clear, the installs pypop into the container Python)
	cd /pypop-source
	./setup.py build

%runscript
	#!/bin/bash
	/usr/bin/env PYTHONPATH=/pypop-source /usr/bin/python2.7 /pypop-source/pypop.py $@

%test
	# Use the runscript to do a simple run
	/singularity -d -c /pypop-source/data/samples/minimal.ini /pypop-source/data/samples/USAFEL-UchiTelle-small.pop

	# The run output contains a date.  Strip it out.
	sed -i -e 's|at: .*$|at: XXXXX|' USAFEL-UchiTelle-small-out.txt
	sed -i -e 's|date=".*"|date="XXXXX"|' USAFEL-UchiTelle-small-out.xml

	# Compare the output with our samples.  Exit if there are differences.
	diff -u /pypop-source/data/singularity-test/USAFEL-UchiTelle-small-out.txt USAFEL-UchiTelle-small-out.txt
	if [ $? -ne 0 ]; then
		exit 1
	fi
	diff -u /pypop-source/data/singularity-test/USAFEL-UchiTelle-small-out.xml USAFEL-UchiTelle-small-out.xml
	if [ $? -ne 0 ]; then
		exit 1
	fi

	# Clean up!
	rm USAFEL-UchiTelle-small-out.txt USAFEL-UchiTelle-small-out.xml
