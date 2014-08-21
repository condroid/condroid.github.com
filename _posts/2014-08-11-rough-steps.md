---
layout: post
title: "Rough steps"
description: ""
category: 
tags: []
---
{% include JB/setup %}

## Compile Kernel (support cgroups & namespaces)

Download *kernel* source code from [**Android X86**](http://git.android-x86.org)to compile,kernel's *config* file is copied from **Android X86**.On this basis,you need following compiler options to surpport LXC's environment.
** (1) About Namespace**  

	CONFIG_NAMESPACES  
	CONFIG_UTS_NS  
	CONFIG_IPC_NS  
	CONFIG_PID_NS  
	CONFIG_NET_NS  

**（2）About Cgroups**
  
	CONFIG_CGROUPS  
	CONFIG_CGROUP_NS  
	ONFIG_CGROUP_DEVICE  
	CONFIG_CGROUP_SCHED  
	CONFIG_CGROUP_CPUACCT  
	CONFIG_CPUSETS  

**（3）About MISC**
  
	CONFIG_VETH  
	CONFIG_MACWLAN  
	CONFIG_VLAN_8021Q  
	CONFIG_SECURITY_FILE_CAPABILITIES  

**（4）Other**
  
	CONFIG_POSIX_MQUEUE
    
## Transplant LXC tools to Android Host
LXC package has executable program and shell script.
**（1）Compile LXC**  

	./configure --prefix=/system/local	
	make
	make install

Note:/usr/local is default prefix of /configure ,and there is no /usr directory in android下,so you need to change it.
  
**（2）Transplant Shell script**  
lxc's script is written in GNU Linux's **bash**.Many tools and commands is non-existent or non-executable.So you need modify as follow:  
1. Statically link a bash procedure,and transpant to android  
2. Copy ubuntu 10.04 file procedure to android  
3. Copy zgrep script to android;zgrep calls ”gzip -cdfq”,and it can't use in Android,replace it to ”gzip -c -d -f”  
4. lxc-create call command id -u from 190;this command can't execute in android,so you should comment revelant code out;lxc-destroy need do some modifications  

**（3）Modify source code**  
conf.c in LXC project calls tmpfile(),which didn't realize in Android's bionic libc.You need write tmpfile_replace(),whose function is same as tmpfile(),and conf.c can call tmpfile_replace()

**（4）Compile LXC again**  
You need compile LXC again after modifying LXC source code; The main process includes following:   
1. Modify LXC_PROJECT/src/lxc/Makefile.am,put new code files to Macro pkginclue\_HEADERS and liblxc\_so\_SOURCES  
2. Call autoconf to generate configure file(you need install autotools and libtools)  
3. Call ./configure and make again

## Run Busybox container
Busybox is a binary executable program,which integrates about 100 frequently-used Linux commands and tools.  
Busybox is viewed as simplest Linux system,which contains all tools to create a complete Linux filesystem hierarchy standard,such as init,mount,mknod,and so on.So,if you can run a Busybox Container,you can also work on our Android LXC environment.  
**（1）Compile statically Busybox**  
You need compile statically a complete busybox to avoid dynamic Shared libraries' error when creating container's rootfs(lxc-create)
1. Download busybox source code from [Busybox](http://www.busybox.net)
2. make menuconfig, --> Build Options, --> Build Busybox as a static binary  
3. make  
4. Put compiled busybox to /system/local/bin directory beneath Host,and add PATH environment variable  

```
adb push bin/busybox /system/local/bin/
export PATH=/system/local/bin:$PATH
```  
**(2) Create rootfs of Busybox**

	lxc-create -t busybox -n bb

**(3) Modify config of Busybox**

	lxc.utsname = bb
	lxc.tty = 1
	lxc.pts = 1
	lxc.rootfs = /system/local/var/lib/lxc/bb/rootfs  
	
	lxc.mount.entry = /lib /system/local/var/lib/lxc/bb/rootfs/lib none ro,bind 0 0
	lxc.mount.entry = /lib /system/local/var/lib/lxc/bb/rootfs/usr/lib none ro,bind 0 0

**(4) Mount cgroup file system**

	for t in `ls /system/cgroup`
	do
		mount -t cgroup -o $t cgroup /system/cgroup/$t
	done

**(5)Solve problem -- No such file or directory: /dev/shm (optional)**

	mkdir -p /dev/shm
	mount -t tmpfs -o nodev,noexec tmpfs /dev/shm


## Run Android JellyBean container
