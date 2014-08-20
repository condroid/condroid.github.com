---
layout: post
title: "Detailed steps"
description: ""
category: 
tags: []
---
{% include JB/setup %}

##Step I  :Compile Android Kernel##
1. Download source code;Kernel's subproject has kernel source code corresponding to the devices here:
	
		https://android.googlesource.com
  	You can find kernel source code path corresponding to your device here
	
		http://source.android.com/source/building-kernels.html
    Download of this git project  is slow,you can use bitbucket or deveo to transfer
2. checkout branch;Change to the source directory,use
	
		$ git branch -a
	View all branches,then use
	
		$ git checkout <branch_name>
	Check codes,here branch_name may have remotes/origin prefix,and there is no need to add -b option,else it will create a new branch
3. Configuration compiling environment;Clone this repo(you may need transfer):
	
		https://android.googlesource.com/platform/prebuilts/gcc/linux-x86/arm/arm-eabi-4.6
    set PATH environment variable,add bin directory beneath repo
4. Compile source code
    
		$ export ARCH=arm
	    $ export SUBARCH=arm
	    $ export CROSS_COMPILE=arm-eabi-
	    $ make xx_defconfig # (Here you can find) config：http://source.android.com/source/building-kernels.html)
	    $ make
    Compiled kernel is `arch/arm/boot/zImage`（Nexus 5 is `zImage-dtb`）
5. Flush a new ROM  
    - Method One:set TARGET_PREBUILT_KERNEL environment variable as compiled kernel,then m make boot.img,using
    		
			$ fastboot flash boot boot.img
		Flush
    - Method Two:copy compiled kernel to out/x/x/x/ directory,named after kernel,then m make boot.img,flush with fastboot

##Step II :Compile Android Source Code##
1. Download source code;Here you can find Android versions which devices support:

		https://developers.google.com/android/nexus/drivers
2. Download driver;Here has driver corresponding to devices:  
	
		https://developers.google.com/android/nexus/drivers
     Get a script after download and extract,put it in Android directory to execute
3. Configuration compiling environment
	    
		System：Ubuntu x86_64 EN
	    Package：
	        build-essential/gcc&g++/lib32stdc++6
	        jdk6
	        python 2.6.x/2.7.x
	        gperf
	        libzip/zlib1g&zlib1g-dev/libzzip-dev
	        lib32z1
	        bison
	        flex
	        libxml2-utils
	        git
	        bc
	        zip
	        squashfs-tools
			libncurses5-dev 
4. Enter Android source code directory;Execute following command to compile source code:
	
		$ source build/envsetup.sh
	    $ lunch # (choose target corresponding to device)
	    $ m
5. Connecting devices;Execute following command to flush a new ROM(you need run as root):
	    
		$ adb reboot bootloader
	    $ fastboot devices
	    $ fastboot flashall -w

##Step III :Kernel Modification##
### Conbinder Driver
1. Enter `drivers/staging/android/` directory
2. Create `conbinder.h` and `conbinder.c`
3. Move the header file of `binder.c` to `conbinder.h`,then `include "conbinder.h"`
4. Remove `static` from `binder_fops` struct's function,then add its declaration in `conbinder.h`
5. Add `CONBINDER_GET_CURRENT_CONTAINER` macro definition in `conbinder.h`(`ioctl` operation gets container's ID in which current process is)
6. Add virtual driver code in `conbinder.c`
7. Modify `binder_ioctl` function in `binder.c`,add treatment codes of `CONBINDER_GET_CURRENT_CONTAINER` command
8. Modify `Kconfig`,add `ANDROID_CONBINDER_IPC` option
9. Modify `Makefile`,add `conbinder.o` compilation configuration


### Conalarm Driver
1. Enter `drivers/rtc/` directory
2. Modify `alarm-dev.c`,add `conalarm_fops` and `conalarm_device` data struct,initialize code and customize `conalarm_open` function
3. Using macro definition-`ANDROID_CONALARM` to control relevant `conalarm` code if compiled
4. Modify `Kconfig`,add `ANDROID_CONALARM_DEV` option
5. Modify `Makefile`,add compilation configuration(`ccflags`) of macro definition `ANDROID_CONALARM`


### Container Driver
1. Enter `drivers/staging/android/` directory
2. Create `container.h` and `container.c`
3. Add macro definition of `ioctl` command in `container.h`
4. Add driver function,data struct and initialization code of container device in `container.c`
5. Modify `Kconfig`,add `ANDROID_CONTAINER` option
6. Modify `Makefile`,add `container.o` compilation configuration


### Compile Configuration
1. Modify `.config`,add following compilation configuration options
	
		ANDROID_CONBINDER_IPC
		ANDROID_CONALARM_DEV
		ANDROID_CONTAINER
		IKCONFIG
		IKCONFIG_PROC
2. According to `lxc-checkconfig`,add compilation configuration options		
3. `According toStep II`,compile

##Step IV :ramdisk modification##
### init.rc
1. Remove  
	
		mount rootfs rootfs / ro remount

2. Add
	
		mount tmpfs tmpfs /run
		symlink /system/bin /bin

3. Add it after PATH environment variable  
	
		:/system/busybox/bin:/system/busybox/sbin:/system/local/bin

4. Add it after LD_LIBRARY_PATH:
	
		:/system/local/lib

5. Add
	
		export ANDROID_CT /system/local/var/lib/lxc/android4.x.x


### uevent.rc
1. Add
	
		/dev/conbinder1			0666	root		root
		...
		/dev/conbinder9			0666	root		root
2. Add
	
		/dev/conalarm           0664   system     radio

3. Add
	
		/dev/container          0666	root		root

##Step V ：LXC Modification and Compilation##
### Code modification

1. Use chroot to replace pivot_root system call

### Cross compilinglxc

1. Download Android NDK
2. Extract NDK,then execute in it
	
		$ build/tools/make-standalone-toolchain.sh
	Find tool chain in /tmp directory
3. Add tool chain directory after PATH environment variable

4. Download `lxc-1.0.0.alpha*` source code

5. Execute in lxc source code
	
		$ autogen.sh
6. Execute
	
		$ ./configure --host=arm-linux-androideabi --prefix=/system/local CC=arm-linux-androideabi-gcc --disable-capabilities
7. Execute 'make',ignore relevant lua wrong
8. Execute
	
		$ sudo make prefix=/system/local install
	You can find compiled procedure in `/system/local`

##Step VI ：Modify system partitions##
## Busybox
Put compiled busybox in system directory

## LXC
Pack the folders in lxc's installation directory,then extractit in /system/local
directory

## Cgroups
1. Create cgroup directory beneath /system/,and Create following directory beneath cgroup
	
		cpuset
		memory
		blkio
		freezer
		device

2. Create script file `mount-cgroups.sh` beneath /system/local/bin,to mount cgroups and ashmem;command is following:
	
		for t in `ls /system/cgroup`
		do
		    mount -t cgroup -o $t cgroup /system/cgroup/$t
		done

		mkdir /dev/shm
		mount -t tmpfs -o nodev,noexec tmpfs /dev/shm

## ServiceManager
1. Modify filter rule of service name,allow registering modified service

## Container configure and root filesystem
1. Create folder `androidx.x.x` beneath `/system/local/var/lib/lxc` to save container system
2. Create file config and directory rootfs within the folder

### config
	
	lxc.utsname = android4.1.2
	lxc.tty = 0
	lxc.rootfs = /system/local/var/lib/lxc/android4.1.2/rootfs
	lxc.cgroup.devices.allow = a

### rootfs
1. Copy all files beneath original system root directory to rootfs directory
2. Create symbolic Links corresponding to original system root directory
3. Create directories beneath system root directory,following the principles:(copy means copying directories of host;empty means creating a empty directory；the same below)
	
		/firmware		copy
		/persist		copy
		/storage		empty
		/config			copy
		/cache			empty
		/acct			empty
		/mnt			empty
		/sys			empty
		/sbin			empty
		/run			empty
		/res			copy
		/proc			empty
		/data			empty
		/root			empty
		/dev			empty
		/system			empty
4. Create device nodes in rootfs/dev,according to filename,device number,permission and owner of all device files
5. Create folder and directory beneath system directory,as following rules:
	
		app					empty
		bin					copy
		build.prop			copy
		busybox				copy
		etc					copy
		fonts				copy
		framework			empty
		lib					empty
		media				empty
		priv-app			empty
		tts					copy
		usr					copy
		vendor				copy
		xbin				copy

### Other Script
1. Create script file `mount-bind.sh` in `android4.x.x` directory,Enter the following command：
	
		mount -o bind /system/app rootfs/system/app
		mount -o bind /system/framework rootfs/system/framework
		mount -o bind /system/lib rootfs/system/lib
		mount -o bind /system/media rootfs/system/media
		mount -o bind /system/priv-app rootfs/system/priv-app

		mount -o bind /dev/conbinder1 rootfs/dev/binder
		mount -o bind /dev/conalarm rootfs/dev/alarm

2. Create script file `share.sh` in `android4.x.x` directory,Enter the following command：
	
		echo "SurfaceFlinger" >>/proc/conbinder/sharedservices

### init
1. Forbid creating /dev directory
2. Forbid mounting tmpfs on /dev directory

### init.rc
1. Forbidden ueventd
2. Forbidden servicemanager

##Step VII :Start Container##
1. Start host
2. Enter shell using following command as root:
	
		# adb root
		# adb shell
3. Execute following command to mount various folders:
	
		# mount-rw.sh
		# mount-cgroups.sh
4. Enter directory in which container is,and execute following command:
	
		# ./mount-bind.sh
		# ./share.sh  
5. Execute following command to clear log:
	
		# dmesg -c
		# logcat -c
6. Execute following command to start container：
	
		lxc-start -n <container name>