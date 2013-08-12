---
layout: post
title: "Android init report 1"
description: ""
category: 
tags: []
---
{% include JB/setup %}
#  Android 启动分析 #
## 1.概述 ##
**Android**虽然被称作一种操作系统，其实它仍然使用的**Linux**的kernel。所以本质上可以说，**Android**是一个适用于移动设备的**Linux**发行版。也就是说，之前的分析**Linux**内核的经验可以拿来用于分析**Android**。不过，值得注意的是，**Android**除去对**Linux**内核的一些改动外，它的大部分代码还是在**Linux**内核启动后的用户空间程序上。所以，分析**Android**代码时，不仅要对**Linux**内核代码熟悉，还要对熟悉**Linux**系统编程要用到的函数，比如`fcntl`、`mmap`、`open`、`read`、`write`等。

## 2. Android启动流程概述##
像大多数的**Linux**发行版那样，在加载启动kernel后，会执行第一个用户空间程序`/init`。  
简单流程就是在`start_kernel`函数的最后调用函数`rest_init`。`rest_init`函数如下

	static noinline void __init_refok rest_init(void)
	{
		......
	    /*这里是关键*/   
		kernel_thread(kernel_init, NULL, CLONE_FS | CLONE_SIGHAND);
		/*看上边*/
		numa_default_policy();
		pid = kernel_thread(kthreadd, NULL, CLONE_FS | CLONE_FILES);
		rcu_read_lock();
		kthreadd_task = find_task_by_pid_ns(pid, &init_pid_ns);
		rcu_read_unlock();
		complete(&kthreadd_done);
		.......
	}

这里通过内核产生线程`kernel_init`--我们所说的0号进程。`kernel_init`函数如下：

	static int __ref kernel_init(void *unused)
	{
		kernel_init_freeable();
		
		......
		/*关键*/
		if (ramdisk_execute_command) {
			if (!run_init_process(ramdisk_execute_command))
				return 0;
			pr_err("Failed to execute %s\n", ramdisk_execute_command);
		}
		/*这里ramdisk_execute_command是有值的，在kernel_init_freeable中设置*/
		......
	
		panic("No init found.  Try passing init= option to kernel. "
		      "See Linux Documentation/init.txt for guidance.");
	}

我们再看`kernel_init`中调用的`kernel_init_freeable`。`kernel_init_freeable`函数如下：

	static noinline void __init kernel_init_freeable(void)
	{
		......
	
		/* Open the /dev/console on the rootfs, this should never fail */
		if (sys_open((const char __user *) "/dev/console", O_RDWR, 0) < 0)
			pr_err("Warning: unable to open an initial console.\n");
	
		(void) sys_dup(0);
		(void) sys_dup(0);
		/*
		 * check if there is an early userspace init.  If yes, let it do all
		 * the work
		 */
		/*这是关键*/
		if (!ramdisk_execute_command)
			ramdisk_execute_command = "/init";//这里设置成/init，android系统的第一个用户态程序
	
		if (sys_access((const char __user *) ramdisk_execute_command, 0) != 0) {
			ramdisk_execute_command = NULL;
			prepare_namespace();
		}
		/*向上看*/
		/*
		 * Ok, we have completed the initial bootup, and
		 * we're essentially up and running. Get rid of the
		 * initmem segments and start the user-mode stuff..
		 */
	
		/* rootfs is available now, try loading default modules */
		load_default_modules();
	}


所以android在启动时会执行`/init`。我们整理一下android的启动流程：

 - `start_kenel`调用`rest_init`
 - `rest_init`调用`kernel_init`
 - `kernel_init`调用`kernel_init_freeable`
 - `kernel_init_freeable`中把`ramdisk_execute_command`设置为`/init`
 - 最后让在`kernel_init`中调用`run_init_process(ramdisk_execute_command)`  

那么`/init`是什么程序呢?
  
`/init`就是**Android**自己的程序了，源代码位于`/system/core/init/init.c`中  

仔细分析发现，该c文件中是有main函数的，说明该文件可以编译链接成用户态的可执行程序——即`/init`

## 3. `/init`分析##
### 3.1 `/init`程序的第一部分 ###

	    umask(0);
	
	        /* Get the basic filesystem setup we need put
	         * together in the initramdisk on / and then we'll
	         * let the rc file figure out the rest.
	         */
	    mkdir("/dev", 0755);
	    mkdir("/proc", 0755);
	    mkdir("/sys", 0755);
		/*dev下的文件系统是tmpfs,之后的null设备和klog设备都是在该文件夹下mknod做成的*/
	    mount("tmpfs", "/dev", "tmpfs", MS_NOSUID, "mode=0755");
	    mkdir("/dev/pts", 0755);
	    mkdir("/dev/socket", 0755);
	    mount("devpts", "/dev/pts", "devpts", 0, NULL);
	    mount("proc", "/proc", "proc", 0, NULL);
	    mount("sysfs", "/sys", "sysfs", 0, NULL);
	
	        /* indicate that booting is in progress to background fw loaders, etc */
	    close(open("/dev/.booting", O_WRONLY | O_CREAT, 0000));


可以注意到的是，由于已经是用户态程序了。代码中可以放心大胆的使用`umask`、`mkdir`、`mount`这些函数，所以熟悉Linux系统编程是很必要的（虽然Android没用glibc，而是bionic，但是接口接口基本一致）。
  
这段代码之简单的挂载了一些必要的文件系统，剩下的要通过解析rc文件在挂载。
### 3.2 `/init/`程序的第二部分 ###

	    open_devnull_stdio();
	    klog_init();
	    property_init();
	
	    get_hardware_name(hardware, &revision);
	
	    process_kernel_cmdline();

#### 3.2.1 函数`open_devnull_stdio`(在`/system/core/init/util.c`中)####

	void open_devnull_stdio(void)
	{
	    int fd;
	    static const char *name = "/dev/__null__";
	    if (mknod(name, S_IFCHR | 0600, (1 << 8) | 3) == 0) {
	        fd = open(name, O_RDWR);
	        unlink(name);
	        if (fd >= 0) {//重定向
	            dup2(fd, 0);
	            dup2(fd, 1);
	            dup2(fd, 2);
	            if (fd > 2) {
	                close(fd);
	            }
	            return;
	        }
	    }
	
	    exit(1);
	}

该函数创建一个null设备，然后通过`dup2`系统调用把它重定向到`stdio`、`stdout`、`stderr`上。注意这时还在`/init`进程中。  

#### 3.2.2函数`klong_init`（在`/system/core/libcutils/klog.c`中）####

	void klog_init(void)
	{
	    static const char *name = "/dev/__kmsg__";
	    if (mknod(name, S_IFCHR | 0600, (1 << 8) | 11) == 0) {
	        klog_fd = open(name, O_WRONLY);//只能写，我发现在klog.c中只有klog_write函数
	        fcntl(klog_fd, F_SETFD, FD_CLOEXEC);
	        unlink(name);
	    }
	}

  
通过`fcntl`设置**FD_CLOEXEC**标志有什么用？(注意当前只有一个这样的**file descriptor flag**)  

`close on exec, not on-fork`, 意为如果对描述符设置了**FD_CLOEXEC**，使用`exec-family`执行的程序里，此描述符被关闭，不能再使用它，但是在使用fork调用的子进程中，此描述符并不关闭，仍可使用。之后我们会发现`/init`中产生子进程都是通过`fork`后在`exeve`实现的，所以子进程（其实就是`init`启动的那些服务）中**klog**文件是关闭的。  

#### 3.2.3函数`property_init`####

 - `property_init`是`init_property_area`的**wrapper**函数
 - `init_property_area`调用`init_workspace`函数并给**libc**中的`__system_property_area__`赋值  

####函数`init_workspace`####

	static int init_workspace(workspace *w, size_t size)
	{
	    void *data;
	    int fd;
	
	        /* dev is a tmpfs that we can use to carve a shared workspace
	         * out of, so let's do that...
	         */
	    fd = open("/dev/__properties__", O_RDWR | O_CREAT, 0600);//没有用mknod
	    if (fd < 0)
	        return -1;
	
	    if (ftruncate(fd, size) < 0)//调整文件大小
	        goto out;
	
	    data = mmap(NULL, size, PROT_READ | PROT_WRITE, MAP_SHARED, fd, 0);
	    if(data == MAP_FAILED)
	        goto out;
	
	    close(fd);
	
	    fd = open("/dev/__properties__", O_RDONLY);
	    if (fd < 0)
	        return -1;
	
	    unlink("/dev/__properties__");
	
	    w->data = data;
	    w->size = size;
	    w->fd = fd;
	    return 0;
	
	out:
	    close(fd);
	    return -1;
	}

`workspace`定义 

    typedef struct {  
        void *data;
        size_t size;
        int fd;
    } workspace;

`pa_workspace`就是类型为`workspace`的全局变量，`init_workspace`函数通过`open`和`mmap`函数创建文件并映射到内存空间，并为字段`data`、`size`、`fd`赋初值，而`data`字段就是刚刚`mmap`映射的空间地址。

####函数`init_property_area`####


	static int init_property_area(void)
	{
	    prop_area *pa;
	
	    if(pa_info_array)
	        return -1;
	
	    if(init_workspace(&pa_workspace, PA_SIZE))
	        return -1;
	
	    fcntl(pa_workspace.fd, F_SETFD, FD_CLOEXEC);
	
	    pa_info_array = (void*) (((char*) pa_workspace.data) + PA_INFO_START);
	
	    pa = pa_workspace.data;
	    memset(pa, 0, PA_SIZE);
	    pa->magic = PROP_AREA_MAGIC;
	    pa->version = PROP_AREA_VERSION;
	
	        /* plug into the lib property services */
	    __system_property_area__ = pa;
	    property_area_inited = 1;
	    return 0;
	}

####`struct prop_area`定义####
  (`/bionic/libc/include/sys/_system_properties.h`)  

    struct prop_area {
        unsigned volatile count;
        unsigned volatile serial;
        unsigned magic;
        unsigned version;
        unsigned reserved[4];
        unsigned toc[1];
    };
通过代码  

    pa = pa_workspace.data;
	......
    __system_property_area__ = pa;
libc库要用到的全局变量`__system_property_area__`的值就被赋成上面讲到的共享内存的地址了，这样方便之后的`/init`产生的各个子进程都能使用libc库的函数访问这个地址。  

可以看出`__system_property_area__`地址开始的部分的内容就是`struct prop_area`所定义的字段。  

自此我们知道`__system_property_area__`、`pa_workspace.data`指向的是同一地址，之所以区分的原因是前者是libc库的全局变量之后的进程都可以通过调用libc库函数使用，而后者是`/init`本身的全局变量可以直接使用。
####`struct prop_info`定义####
  (`/bionic/libc/include/sys/_system_properties.h`)  


    struct prop_info {
        char name[PROP_NAME_MAX];
        unsigned volatile serial;
        char value[PROP_VALUE_MAX];
    };
该结构就是property system中的key/alue键值对，也是全局变量`pa_info_array`的类型。  

通过代码

    pa_info_array = (void*) (((char*) pa_workspace.data) + PA_INFO_START);
使得`pa_info_array`指向那块共享内存地址后面`PA_INFO_START`处。
  

整个property system的数据结构如图: 
 
![property_system](http://img.my.csdn.net/uploads/201101/13/0_12949281482cTc.gif)
这里只是对property system的数据结构的初始化，真正的服务还要在之后启动。

#### 3.2.4 函数`get_hardware_name`####
`/system/core/init/util.c`

	void get_hardware_name(char *hardware, unsigned int *revision)
	{
	 	......
	    fd = open("/proc/cpuinfo", O_RDONLY);
	    if (fd < 0) return;
	
	    n = read(fd, data, 1023);
	    close(fd);
	    if (n < 0) return;
	
	    data[n] = 0;
	    hw = strstr(data, "\nHardware");
	    rev = strstr(data, "\nRevision");
	
	    if (hw) {
	        x = strstr(hw, ": ");
	 		......
	    }
	
	    if (rev) {
	        x = strstr(rev, ": ");
	     	......
	    }
	}

函数很简单就是通过读取`/proc/cpuinfo`中的信息获得`hardware`和`revision`信息。函数的参数指向的是全局变量。
#### 3.2.5 函数`process_kernel_cmdline`####
`/system/core/init/init.c`


	static void process_kernel_cmdline(void)
	{
		......
	    import_kernel_cmdline(0, import_kernel_nv);
	    if (qemu[0])//qemu是`/init`的全局变量
	        import_kernel_cmdline(1, import_kernel_nv);
	
	    export_kernel_boot_props();
	}

该函数分两部分，第一部分读取`kernel cmdline`，第二部分输出`kernel cmdline`.

####函数`import_kernel_cmdline`(在`/system/core/init/util.c`中)####

	void import_kernel_cmdline(int in_qemu,
	                           void (*import_kernel_nv)(char *name, int in_qemu))
	{
	    char cmdline[1024];
	    char *ptr;
	    int fd;
	
	    fd = open("/proc/cmdline", O_RDONLY);
	    if (fd >= 0) {
	        int n = read(fd, cmdline, 1023);
			.....
	        close(fd);
	    } else {
	        cmdline[0] = 0;
	    }
	
	    ptr = cmdline;
	    while (ptr && *ptr) {
	        char *x = strchr(ptr, ' ');
	        if (x != 0) *x++ = 0;
	        import_kernel_nv(ptr, in_qemu);
	        ptr = x;
	    }
	}

函数很简单，就是读取`/proc/cmdline`中内容，以空格为分隔符分解字符串，把分得的字符串传给`import_kernel_nv`函数。（值得注意的是`import_kernel_nv`有两个定义，此处通过参数传进来的是`/system/core/init/init.c`中的`static`原型，在同目录下的`ueventd.c`中也有）  

####函数`import_kernel_nv`####


	static void import_kernel_nv(char *name, int in_qemu)
	{
	    char *value = strchr(name, '=');
	
	    if (value == 0) return;
	    *value++ = 0;
	    if (*name == 0) return;
	
	    if (!in_qemu)
	    {
	        /* on a real device, white-list the kernel options */
	        if (!strcmp(name,"qemu")) {
	            strlcpy(qemu, value, sizeof(qemu));
	        } else if (!strcmp(name,"androidboot.console")) {
	            strlcpy(console, value, sizeof(console));
	        } else if (!strcmp(name,"androidboot.mode")) {
	            strlcpy(bootmode, value, sizeof(bootmode));
	        } else if (!strcmp(name,"androidboot.serialno")) {
	            strlcpy(serialno, value, sizeof(serialno));
	        } else if (!strcmp(name,"androidboot.baseband")) {
	            strlcpy(baseband, value, sizeof(baseband));
	        } else if (!strcmp(name,"androidboot.carrier")) {
	            strlcpy(carrier, value, sizeof(carrier));
	        } else if (!strcmp(name,"androidboot.bootloader")) {
	            strlcpy(bootloader, value, sizeof(bootloader));
	        } else if (!strcmp(name,"androidboot.hardware")) {
	            strlcpy(hardware, value, sizeof(hardware));
	        } else if (!strcmp(name,"androidboot.modelno")) {
	            strlcpy(modelno, value, sizeof(modelno));
	        }
	    } else {
	        /* in the emulator, export any kernel option with the
	         * ro.kernel. prefix */
	        char  buff[32];
	        int   len = snprintf( buff, sizeof(buff), "ro.kernel.%s", name );
	        if (len < (int)sizeof(buff)) {
	            property_set( buff, value );
	        }
	    }
	}

该函数分两种情况处理传进来的字符串。

 1. 不再模拟器中时，解析字符串，赋值给`qemu`,`console`等`/init`的全局变量。  

 2. 在模拟器中时，则给字符串添加`ro.kernel.`的前缀，然后添加到`property system`中。

####函数`export_kernel_boot_props`(在/system/core/init/init.c中)####

	static void export_kernel_boot_props(void)
	{
	    char tmp[PROP_VALUE_MAX];
	    const char *pval;
	    unsigned i;
	    struct {
	        const char *src_prop;
	        const char *dest_prop;
	        const char *def_val;
	    } prop_map[] = {
	        { "ro.boot.serialno", "ro.serialno", "", },
	        { "ro.boot.mode", "ro.bootmode", "unknown", },
	        { "ro.boot.baseband", "ro.baseband", "unknown", },
	        { "ro.boot.bootloader", "ro.bootloader", "unknown", },
	    };
	
	    for (i = 0; i < ARRAY_SIZE(prop_map); i++) {
	        pval = property_get(prop_map[i].src_prop);
	        property_set(prop_map[i].dest_prop, pval ?: prop_map[i].def_val);
	    }
	
	    pval = property_get("ro.boot.console");
	    if (pval)
	        strlcpy(console, pval, sizeof(console));
	
	    /* save a copy for init's usage during boot */
	    strlcpy(bootmode, property_get("ro.bootmode"), sizeof(bootmode));
	
	    /* if this was given on kernel command line, override what we read
	     * before (e.g. from /proc/cpuinfo), if anything */
	    pval = property_get("ro.boot.hardware");
	    if (pval)
	        strlcpy(hardware, pval, sizeof(hardware));
	    property_set("ro.hardware", hardware);
	
	    snprintf(tmp, PROP_VALUE_MAX, "%d", revision);
	    property_set("ro.revision", tmp);
	
	    /* TODO: these are obsolete. We should delete them */
	    if (!strcmp(bootmode,"factory"))
	        property_set("ro.factorytest", "1");
	    else if (!strcmp(bootmode,"factory2"))
	        property_set("ro.factorytest", "2");
	    else
	        property_set("ro.factorytest", "0");
	}

该函数就是把读取的`kernel cmdline`赋值给`property system`.

### 3.3 `/init/`程序的第三部分 ###

		/*is_charger和bootmode的意义是一样的，把bootmode转换成is_charger的init变量方便之后的判断*/
	    is_charger = !strcmp(bootmode, "charger");
	
	    INFO("property init\n");
	    if (!is_charger)
	        property_load_boot_defaults();//装载/default.prop
	
	    INFO("reading config file\n");
	    init_parse_config_file("/init.rc");//解析/init.rc文件
	
	    action_for_each_trigger("early-init", action_add_queue_tail);
	
	    queue_builtin_action(wait_for_coldboot_done_action, "wait_for_coldboot_done");
	    queue_builtin_action(keychord_init_action, "keychord_init");
	    queue_builtin_action(console_init_action, "console_init");
	
	    /* execute all the boot actions to get us started */
	    action_for_each_trigger("init", action_add_queue_tail);
	
	    /* skip mounting filesystems in charger mode */
	    if (!is_charger) {
	        action_for_each_trigger("early-fs", action_add_queue_tail);
	        action_for_each_trigger("fs", action_add_queue_tail);
	        action_for_each_trigger("post-fs", action_add_queue_tail);
	        action_for_each_trigger("post-fs-data", action_add_queue_tail);
	    }
	
	    queue_builtin_action(property_service_init_action, "property_service_init");
	    queue_builtin_action(signal_init_action, "signal_init");
	    queue_builtin_action(check_startup_action, "check_startup");
	
	    if (is_charger) {
	        action_for_each_trigger("charger", action_add_queue_tail);
	    } else {
	        action_for_each_trigger("early-boot", action_add_queue_tail);
	        action_for_each_trigger("boot", action_add_queue_tail);
	    }
	
	        /* run all property triggers based on current state of the properties */
	    queue_builtin_action(queue_property_triggers_action, "queue_property_triggers");

这里**charger mode**就是**android**的充电模式，就是没开机，屏幕显示一个不断充电的图标的模式。
给函数做了以下事情（我们假设是非充电模式）：

 1. 装载默认的prop文件，在文件一般是`/default.prop`

 2. 解析`/init.rc`文件，在`/init`中注册**Action** 和 **Service**,如何解析`/init.rc`，之后做详细分析。

 3. 接下来的一些系列函数把从1)init.rc中注册的**Action**以及2)一些**Builtin Action**加入到**Action Queue**中，因为只有**Action Queue**中的**Action**才会被执行。执行顺序是先进先出的队列模式。

其实本部分是**Android**启动的重点内容，我会另开一篇文章详细分析的。

### 3.4 `/init/`程序的第四部分 ###

	    for(;;) {
	        int nr, i, timeout = -1;
	
	        execute_one_command();
	        restart_processes();
	
	        if (!property_set_fd_init && get_property_set_fd() > 0) {
	            ufds[fd_count].fd = get_property_set_fd();
	            ufds[fd_count].events = POLLIN;
	            ufds[fd_count].revents = 0;
	            fd_count++;
	            property_set_fd_init = 1;
	        }
	        if (!signal_fd_init && get_signal_fd() > 0) {
	            ufds[fd_count].fd = get_signal_fd();
	            ufds[fd_count].events = POLLIN;
	            ufds[fd_count].revents = 0;
	            fd_count++;
	            signal_fd_init = 1;
	        }
	        if (!keychord_fd_init && get_keychord_fd() > 0) {
	            ufds[fd_count].fd = get_keychord_fd();
	            ufds[fd_count].events = POLLIN;
	            ufds[fd_count].revents = 0;
	            fd_count++;
	            keychord_fd_init = 1;
	        }
	
	        if (process_needs_restart) {
	            timeout = (process_needs_restart - gettime()) * 1000;
	            if (timeout < 0)
	                timeout = 0;
	        }
			/*只要还有action要执行，timeout就是0，也就是不等待*/
	        if (!action_queue_empty() || cur_action)
	            timeout = 0;
	
	        nr = poll(ufds, fd_count, timeout);
	        if (nr <= 0)
	            continue;
	
	        for (i = 0; i < fd_count; i++) {
	            if (ufds[i].revents == POLLIN) {
	                if (ufds[i].fd == get_property_set_fd())
	                    handle_property_set_fd();
	                else if (ufds[i].fd == get_keychord_fd())
	                    handle_keychord();
	                else if (ufds[i].fd == get_signal_fd())
	                    handle_signal();
	            }
	        }
	    }

`/init`的最后一部分就是在`for`循环中不断从**Action Queue**中取得**Action**来执行**Action**中的命令。  

       execute_one_command();
       restart_processes();  

在`execute_one_command`函数中执行**Action**中的**Command**（关于**Action**的结构，我会在详细介绍`/init`第三部分程序的文章中分析的）。然后在`restart_processes`中运行需要重启的服务。

循环的最后通过`poll`处理`property_set_fd`、`signal_fd`、`keychord_fd`文件发生的**POLLIN**事件。这些文件的建立也是通过之前的**Action**中执行的命令建立的。
