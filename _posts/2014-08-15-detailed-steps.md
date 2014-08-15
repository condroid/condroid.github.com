---
layout: post
title: "Detailed steps"
description: ""
category: 
tags: []
---
{% include JB/setup %}

##Step I  :编译Android内核##
1. 下载源代码。这里的kernel子项目中有各个设备对应的kernel源代码：
	
		https://android.googlesource.com
  	这里可以找到设备对应的内核源代码路径：
	
		http://source.android.com/source/building-kernels.html
    这个git项目下载速度比较慢，可以用bitbucket或者deveo中转
2. checkout branch。进入源代码目录，使用
	
		$ git branch -a
	查看所有的branch，然后使用
	
		$ git checkout <branch_name>
	检出代码，此处的branch_name可能有remotes/origin前缀，而且不需要加-b选项，如果加了将会创建一个新的branch
3. 配置编译环境。clone这个repo（可能也需要中转）：
	
		https://android.googlesource.com/platform/prebuilts/gcc/linux-x86/arm/arm-eabi-4.6
    设置PATH环境变量，添加repo下边的bin目录
4. 编译源代码
    
		$ export ARCH=arm
	    $ export SUBARCH=arm
	    $ export CROSS_COMPILE=arm-eabi-
	    $ make xx_defconfig # 这里可以查到config：http://source.android.com/source/building-kernels.html)
	    $ make
    编译好的kernel为`arch/arm/boot/zImage`（Nexus 5为`zImage-dtb`）
5. 刷机  
    - 方法一：设置TARGET_PREBUILT_KERNEL环境变量为编译好的kernel，然后m制作boot.img，用
    		
			$ fastboot flash boot boot.img
		刷入
    - 方法二：将编译好的kernel copy到out/x/x/x/目录，命名为kernel，然后m制作boot.img，用fastboot刷入

##Step II :编译Android源代码##
1. 下载源代码。这里可以查到设备支持的Android版本：

		https://developers.google.com/android/nexus/drivers
2. 下载驱动。这里有设备对应的驱动  
	
		https://developers.google.com/android/nexus/drivers
    下载完成之后解压得到一个脚本，放到Android源代码目录下执行即可
3. 配置编译环境
	    
		系统：Ubuntu x86_64 EN
	    软件包：
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
4. 进入Android源代码目录，执行以下步骤编译源代码：
	
		$ source build/envsetup.sh
	    $ lunch # 选择与设备代号对应的target
	    $ m
5. 把设备插上，执行以下步骤刷机(需要root权限)：
	    
		$ adb reboot bootloader
	    $ fastboot devices
	    $ fastboot flashall -w

##Step III :内核修改##
### conbinder驱动
1. 进入`drivers/staging/android/`目录
2. 创建`conbinder.h`和`conbinder.c`
3. 将`binder.c`中的头文件移到`conbinder.h`中，然后`include "conbinder.h"`
4. 将`binder_fops`结构中包含的函数去掉`static`修饰，然后在`conbinder.h`中添加其声明
5. 在`conbinder.h`中添加`CONBINDER_GET_CURRENT_CONTAINER`宏定义（`ioctl`获取当前进程所在container编号的命令）
6. 在`conbinder.c`中添加虚拟驱动代码
7. 修改`binder.c`中的`binder_ioctl`函数，增加`CONBINDER_GET_CURRENT_CONTAINER`命令的处理代码
8. 修改`Kconfig`，增加`ANDROID_CONBINDER_IPC`选项
9. 修改`Makefile`，增加`conbinder.o`的编译配置


### conalarm驱动
1. 进入`drivers/rtc/`目录
2. 修改`alarm-dev.c`，增加`conalarm_fops`和`conalarm_device`数据结构以及初始化代码，并且自定义`conalarm_open`函数
3. 将`conalarm`相关代码是否编译用宏定义`ANDROID_CONALARM`控制
4. 修改`Kconfig`，增加`ANDROID_CONALARM_DEV`选项
5. 修改`Makefile`，增加`ANDROID_CONALARM`宏定义的编译配置（`ccflags`）


### container驱动
1. 进入`drivers/staging/android/`目录
2. 创建`container.h`和`container.c`
3. 在`container.h`中添加各`ioctl`命令的宏定义
4. 在`container.c`中添加container设备的驱动函数，数据结构和初始化代码
5. 修改`Kconfig`，增加`ANDROID_CONTAINER`选项
6. 修改`Makefile`，增加`container.o`的编译配置


### 编译配置
1. 修改`.config`，增加以下配置选项
	
		ANDROID_CONBINDER_IPC
		ANDROID_CONALARM_DEV
		ANDROID_CONTAINER
		IKCONFIG
		IKCONFIG_PROC
2. 根据`lxc-checkconfig`的要求增加编译配置选项		
3. `按照Step II`编译

##Step IV :ramdisk修改##
### init.rc
1. 去掉  
	
		mount rootfs rootfs / ro remount

2. 添加
	
		mount tmpfs tmpfs /run
		symlink /system/bin /bin

3. 在PATH环境变量后面添加  
	
		:/system/busybox/bin:/system/busybox/sbin:/system/local/bin

4. 在LD_LIBRARY_PATH后面添加
	
		:/system/local/lib

5. 添加
	
		export ANDROID_CT /system/local/var/lib/lxc/android4.x.x


### uevent.rc
1. 添加
	
		/dev/conbinder1			0666	root		root
		...
		/dev/conbinder9			0666	root		root
2. 添加
	
		/dev/conalarm           0664   system     radio

3. 添加
	
		/dev/container          0666	root		root

##Step V ：lxc修改和编译##
### 代码修改

1. 使用chroot代替pivot_root系统调用

### 交叉编译lxc

1. 下载Android NDK
2. 解压NDK之后在其中执行
	
		$ build/tools/make-standalone-toolchain.sh
	然后在/tmp目录中找到tool chain
3. 添加tool chain目录到PATH环境变量

4. 下载`lxc-1.0.0.alpha*`源代码

5. 在lxc源代码中执行
	
		$ autogen.sh
6. 执行
	
		$ ./configure --host=arm-linux-androideabi --prefix=/system/local CC=arm-linux-androideabi-gcc --disable-capabilities
7. 执行make，忽略lua相关的错误
8. 执行
	
		$ sudo make prefix=/system/local install
	在`/system/local`下面可以找到编译好的程序

##Step VI ：system分区修改##
## Busybox
将编译好的busybox放到system目录

## LXC
将lxc的安装目录下面的各个文件夹打包，解压到/system/local目录

## Cgroups
1. 在/system/下面创建cgroup目录，并在其中创建以下目录
	
		cpuset
		memory
		blkio
		freezer
		device

2. 在/system/local/bin中创建脚本mount-cgroups.sh用于挂载cgroups和ashmem，命令为
	
		for t in `ls /system/cgroup`
		do
		    mount -t cgroup -o $t cgroup /system/cgroup/$t
		done

		mkdir /dev/shm
		mount -t tmpfs -o nodev,noexec tmpfs /dev/shm

## ServiceManager
1. 修改服务名过滤规则，允许注册修改过的服务

## Container配置和根文件系统
1. 在`/system/local/var/lib/lxc`下创建文件夹`androidx.x.x`用于存储Container系统
2. 在文件夹中创建config文件和rootfs目录

### config
	
	lxc.utsname = android4.1.2
	lxc.tty = 0
	lxc.rootfs = /system/local/var/lib/lxc/android4.1.2/rootfs
	lxc.cgroup.devices.allow = a

### rootfs
1. 将原系统根目录下面的文件全部copy到rootfs目录
2. 创建与原系统根目录一致的符号链接
3. 按照以下规则创建根目录下的各目录：（copy表示直接复制主机的相应目录，empty表示创建空目录，下同）
	
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
4. 按照/dev下的各个设备文件的文件名、设备号、权限和所有者在rootfs/dev下创建各个设备节点
5. 按照以下规则创建system目录下的文件和目录
	
		app					empty
		bin					copy
		build.prop			copy
		busybox				copy
		etc					copy
		fonts				copy
		framework			empty
		lib					empty
		media				empty
		priv-app				empty
		tts					copy
		usr					copy
		vendor				copy
		xbin				copy

### 其它脚本
1. 在android4.x.x目录下创建脚本文件mount-bind.sh，输入以下命令
	
		mount -o bind /system/app rootfs/system/app
		mount -o bind /system/framework rootfs/system/framework
		mount -o bind /system/lib rootfs/system/lib
		mount -o bind /system/media rootfs/system/media
		mount -o bind /system/priv-app rootfs/system/priv-app

		mount -o bind /dev/conbinder1 rootfs/dev/binder
		mount -o bind /dev/conalarm rootfs/dev/alarm

2. 在android4.x.x目录下创建脚本文件share.sh，输入以下命令
	
		echo "SurfaceFlinger" >>/proc/conbinder/sharedservices

### init
1. 禁止创建/dev目录
2. 禁止挂载tmpfs到/dev目录

### init.rc
1. 禁用ueventd
2. 禁用servicemanager

##Step VII :启动Container##
1. 启动主机
2. 使用以下命令以root权限进入shell：
	
		# adb root
		# adb shell
3. 执行以下命令mount各种文件夹：
	
		# mount-rw.sh
		# mount-cgroups.sh
4. 进入container所在目录，执行以下命令：
	
		# ./mount-bind.sh
		# ./share.sh  
5. 执行以下命令清空日志：
	
		# dmesg -c
		# logcat -c
6. 执行以下命令启动container：
	
		lxc-start -n <container name>