---
layout: page
title: Introduction
tagline: This is homepage
---
{% include JB/setup %}

Condroid (And**roid** + **Con**tainer) is a lightweight mobile virtualization solution based on OS-level virtualization method. It supports multiple isolated Android user-space instances simultaneously, which enables two or more individual, completely independent, and secure personas to coexist seamlessly on one device.  

## Requirements
（1)Android X86,version: Jelly Bean 4.2.0  
（2)Ubuntu 10.04 32bit (cross-compile)  
（3)ADB 

## Compile Kernel (support cgroups & namespaces)

从[**Android X86**](http://git.android-x86.org)上下载*kernel*源代码包进行编译，内核*config*文件拷贝自 **Android X86**，在此基础上为了支持LXC的环境需要开启如下的编译选项。  
**（1）Namespace相关**  

	CONFIG_NAMESPACES  
	CONFIG_UTS_NS  
	CONFIG_IPC_NS  
	CONFIG_PID_NS  
	CONFIG_NET_NS  

**（2）Cgroups相关**
  
	CONFIG_CGROUPS  
	CONFIG_CGROUP_NS  
	ONFIG_CGROUP_DEVICE  
	CONFIG_CGROUP_SCHED  
	CONFIG_CGROUP_CPUACCT  
	CONFIG_CPUSETS  

**（3）MISC相关**
  
	CONFIG_VETH  
	CONFIG_MACWLAN  
	CONFIG_VLAN_8021Q  
	CONFIG_SECURITY_FILE_CAPABILITIES  

**（4）Other**
  
	CONFIG_POSIX_MQUEUE
    
## Transplant LXC tools to Android Host
LXC软件包里既有可执行程序，也有shell脚本。  
**（1）编译LXC**  

	./configure --prefix=/system/local	
	make
	make install

注意./configure默认的prefix是/usr/local，而android下没有/usr目录，故需要修改。  
**（2）Shell脚本移植**  
lxc的脚本基本是以GNU Linux的**bash** 为环境写就的。很多工具和命令在Android的**busybox**和**mksh**的环境下不存在或不可执行。所以，需要做如下修改：  
1. 静态链接了一个bash程序，移植到了android下。  
2. 将ubuntu 10.04的file程序拷贝到了android下。  
3. 拷贝zgrep脚本到android。zgrep中调用的”gzip -cdfq”在Android下不能使用，修改成”gzip -c -d -f”  
4.  lxc-create第190处调用了id -u命令，这一句在android下不能执行，注释掉相应代码。lxc-destroy需要做相应的修改。  

**（3）源代码的修改**  
LXC项目中conf.c中调用了tmpfile()这个API提供的函数。该函数在Android的bionic libc中没有实现。需要自己写一个tmpfile_replace()，功能和tmpfile()相同，让conf.c调用tmpfile_replace()。

**（4）重新编译LXC**  
修改完LXC源代码后，需要重新编译，主要步骤包括：  
1. 修改LXC_PROJECT/src/lxc/Makefile.am, 将新添加的代码文件加到宏pkginclue\_HEADERS和liblxc\_so\_SOURCES中。  
2. 调用autoconf重新生成configure文件（需要安装autotools和libtools）。  
3. 重新调用./configure和make

## Run Busybox container
Busybox是一个二进制可执行程序，里面集成压缩了Linux的许多工具,大约包括了一百多个常用的Linux命令和工具。  
Busybox被视为最简单的Linux系统，因为其包含了构建一个完整Linux文件系统层级的所有工具，如init，mount，mknod等，所以运行起一个Busybox Container可以验证我们的Android LXC环境是否能正常工作了。  
**（1）静态编译Busybox**  
为了在创建Container的rootfs时（lxc-create），不出现动态共享库错误，需要静态编译一个完整的busybox  
1. 从[Busybox](http://www.busybox.net)官网上下载busybox源码;  
2. make menuconfig, --> Build Options, --> Build Busybox as a static binary;  
3. make  
4. 将编译出来的busybox，放到Host的/system/local/bin目录下，并添加环境变量  

```
adb push bin/busybox /system/local/bin/
export PATH=/system/local/bin:$PATH
```  
**(2) 创建Busybox的rootfs**

	lxc-create -t busybox -n bb

**(3) 修改Busybox的config**

	lxc.utsname = bb
	lxc.tty = 1
	lxc.pts = 1
	lxc.rootfs = /system/local/var/lib/lxc/bb/rootfs  
	
	lxc.mount.entry = /lib /system/local/var/lib/lxc/bb/rootfs/lib none ro,bind 0 0
	lxc.mount.entry = /lib /system/local/var/lib/lxc/bb/rootfs/usr/lib none ro,bind 0 0

**(4) 挂载cgroup文件系统**

	for t in `ls /system/cgroup`
	do
		mount -t cgroup -o $t cgroup /system/cgroup/$t
	done

**(5)解决No such file or directory: /dev/shm的问题(optional)**

	mkdir -p /dev/shm
	mount -t tmpfs -o nodev,noexec tmpfs /dev/shm
## Run Android JellyBean container
**(1) **

