---
layout: post
title: "Linux Container Research Report"
description: "LXC代码阅读文档整理"
category: 
tags: []
---
{% include JB/setup %}

## 1. 综述

lxc是Linux Container的用户态工具包。其代码由三部分组成：

1. shell脚本，部分lxc命令是用shell脚本写就的。
1. c语言代码，最终编译成可执行文件。这部分代码也用来提供最终的lxc命令。但是这些代码以处理命令行参数，读取配置文件等为主。
1. c语言代码，最终编译为动态链接库liblxc.so。该动态库提供了lxc项目的大部分功能，如配置文件分析、日志记录、容器的创建、通信等。lxc命令的各项功能基本都是通过调用liblxc.so中的函数来完成的。

在命名习惯上， 生成lxc命令的c源文件都有``lxc_``的前缀。而生成liblxc.so的c源文件则没有该前缀。

## 2. lxc-start

lxc-start的执行过程大致就是两步：

1. 解析命令行和配置文件
1. 创建新的进程运行container

### 2.1 解析命令行和配置文件

lxc-start的main函数在lxc_start.c中。从main的流程中能大致窥探出lxc-start的执行过程。首先调用``lxc_arguments_parse``来分析命令行，再调用``lxc_config_read``来解析配置文件，等获取好足够的信息后，调用``lxc_start``开始了container。

#### lxc_arguments_parse

函数的实现位于arguments.c中。通过该函数的执行，命令行参数中的信息被存放到了类型为``lxc_arguments``的变量my_args中。命令行参数中有几个我们可以注意一下：

 - "-n" 指定了container的名字
 - "-c" 指定了某个文件作为container的console
 - "-s" 在命令行中指定key=value的config选项
 - "-o" 指定输出的log文件
 - "-l" log的打印级别。用"-l DEBUG"命令行参数，log打印的信息最详细

``lxc_arguments``中有一个字段``lxcpath``指定了lxc container的存放路径。可以在命令参数-P选项中设置。如果不设置，会启用默认参数。该默认参数是在编译lxc代码的时候指定的，一般情况下为"/usr/local/var/lib/lxc"或"/var/lib/lxc"。在本文中，我们一律用*LXCPATH*来表示该路径。

另外，我们约定用*CT-NAME*表示-n参数指定的container的名称。

#### lxc_config_read

它的实现在confile.c中。逐行读取配置文件。并调用confile.c下的``parse_line``来每行做解析。因为配置文件每行都是key=value的形式的，所以``parse_line``的主要内容是找到"=",分析出(key, value)对并做处理。

配置文件的路径由-f参数指定。不指定则从*LXCPATH/CT-NAME/config*中读取。

confile.c的真正核心内容在与95行定义的一个结构体数组
    
    static struct lxc_config_t config[] = {
        { "lxc.arch",                 config_personality          },
        { "lxc.pts",                  config_pts                  },
    	{ "lxc.tty",                  config_tty                  },
    	{ "lxc.devttydir",            config_ttydir               },
        .....
    };
    
其中``lxc_config_t``结构体的定义如下:

    typedef int (*config_cb)(const char *key, const char *value, struct lxc_conf *lxc_conf);
    struct lxc_config_t {
        char* name;
        config_cb cb;
    };
    
``lxc_config_t``结构体的name字段给定了key的值，回调函数cb给出了对应key的处理方法。整个config结构体数组就是键值与对应动作的一个查找表。

现在我们来考虑一个场景。我们在配置文件中写入了``lxc.tty = 4``。``parse_line``会解析出(lxc.tty, 4)的序对。到config中查询得出其对应的处理函数是``config_tty``,于是就开始调用``config_tty``。

函数指针``config_cb``一共有三个参数，``key``指的是如``lxc.tty``之类的键，而``value``指的是如``4``之类的值。``lxc_conf``用来存放config文件的分析结果。

lxc_config_read读取好的配置文件放在类型为lxc_conf的结构体指针conf。lxc_conf的定义在conf.h中。

### 2.2 调用lxc_start

让我们再次回到main函数。前面我们通过分析命令行参数和配置文件，收集了container的一系列信息，接下来就该启动container了。

main函数255行的``lxc_start``打响了了启动container的第一枪。``lxc_start``的实现在start.c中，函数原型如下：
    
    int lxc_start(const char* name, char *const argv[], struct lxc_conf *conf, const char *lxcpath)

四个参数的含义如下：

 - name *CT-NAME*
 - argv container要执行的第一个命令。可以通过命令行参数指定, 如“lxc-start -n android4.2 /init”，这里的argv就会是{"/init", NULL}。如果没有指定，默认是{"/sbin/init", NULL}
 - conf 前面解析好的container配置文件中指定的配置信息。
 - lxcpath LXCPATH

``lxc_start``首先调用``lxc_check_inherited``来关闭所有打开的文件句柄。0(stdin), 1(stdout), 2(stder)和日志文件除外。紧接着就调``__lxc_start``。

#### __lxc_start
其原型如下：

    int __lxc_start(const char* name, struct lxc_conf *conf, struct lxc_operators *op, void *data, const char *lxcpath)

``lxc_operators``结构体定义如下：
    
    struct lxc_operations {
        int (*start)(struct lxc_handler *, void *);
	    int (*post_start)(struct lxc_handler *, void *);
    };

各个参数含义如下：

 - name *CT-NAME*
 - conf container配置信息
 - op 用lxc_operator结构体来存放了两个函数指针start和post_start。这两个指针分别指向start.c的start函数和post_start函数。
 - data start_args类型的结构体，唯一的成员变量argv指向了lxc_start的实参argv，也就是container要执行的init。
 - lxcpath *LXCPATH*

``__lxc_start``代码不复杂。我们将比较重要的几个函数调用抽出来看。

#### lxc_init

``__lxc_start``调用的第一个函数，用来初始化lxc_handler结构体。传入的三个参数依次为：

 - name *CT-NAME*
 - conf container的配置信息
 - lxcpath *LXCPATH*

函数先新分配一个lxc_handler的结构体handler，设置其conf、lxcpath和name字段。然后调用了``lxc_command_init``新创建了一个socket并listen之，新建socket的句柄放置在handler->maincmd_fd中。该socket的作用应为接受外部命令。``lxc_command_init``的实现在commands.c中。其分析可以详见模块**commands.c**部分。

接着是``lxc_set_state``。它将STARTING的状态消息写入到另一个socket中。``lxc_set_state``的实现调用了monitor.c的``lxc_moitor_send_state``。对其分析可以参见**monitor.c**模块。

接着是部分环境变量的设置：``LXC_NAME, LXC_CONFIG_FILE, LXC_ROOTFS_MOUNT, LXC_ROOTFS_PATH, LXC_CONSOLE, LXC_CONSOLE_LOGPATH``。

接下来的四件事情：

 1. 调用``run_lxc_hooks``运行pre-start的脚本。
 2. 调用``lxc_create_tty``创建tty
 3. 调用``lxc_create_console``创建console
 4. 调用``setup_signal_fd``处理进程的信号响应

我们来重点分析第二步和第三步

#### 终端设备的创建
##### 1. tty

``lxc_create_tty``通过调用openpty的命令来为container分配tty设备。conf->tty参数指定了要分配的tty的个数。conf->tty_info结构体用来存放分配好的tty的相关信息。

如果conf->tty的值是4,那么lxc_create_tty执行完之后的结果是：

    conf->tty_info->nb_tty: 4
    conf->tty_info->pty_info: 大小为4的类型为lxc_pty_info的数组的头指针

lxc_pty_info的定义如下：
    
    struct lxc_pty_info {
        char name[MAXPATHLEN];
	    int master;
	    int slave;
	    int busy;
    };

``conf->tty_info->pty_info``的每一项都记录了一个新创建pty的信息，master表示pty master的句柄，slave表示slave的句柄，name表示pty slave的文件路径，即"/dev/pts/N"。

##### 2. console
``lxc_create_console``同样调用openpty用来创建console设备。创建好的console设备信息存放在类型为``lxc_cosnole``的结构体变量``conf->console``中。

lxc_console的结构体定义如下：

    struct lxc_console {
        int slave;
	    int master;
	    int peer;
	    char *path;
	    char *log_path;
	    int log_fd;
	    char name[MAXPATHLEN];
	    struct termios *tios;
    };

各个参数的含义如下：

 - slave 新创建pty的slave
 - master 新创建pty的master
 - path console文件路径，可以通过配置文件"lxc.console.path"或者命令行参数-c指定。默认为"/dev/tty"
 - log_path console的日志路径
 - peer 打开path, 返回句柄放入peer中。
 - log_fd 打开log_path, 返回句柄放入log_fd中。
 - name slave的路径。
 - tios 存放tty旧的控制参数。

#### lxc_spawn

让我们继续回到``__lxc_start``的主流程。前面通过调用``lxc_init``初始化了一个lxc_handler的结构体handler，然后在主流程里，又将传入的ops参数和data参数赋值给了handler的ops字段和data字段。接着就以handler为参数，调用了``lxc_spawn``。

``lxc_spawn``是启动新的容器的核心。进程通过Linux系统调用clone创建了拥有自己的PID、IPC、文件系统等独立的命名空间的新进程。然后在新的进程中执行``/sbin/init``。接下来我们来看具体过程。

1. 首先调用``lxc_sync_init``来为将来父子进程同步做初始化。
1. 准备clone调用需要的flag。各个flags如下：
	- ``CLONE_NEWUTS`` 子进程指定了新的utsname，即新的“计算机名”
	- ``CLONE_NEWPID`` 子进程拥有了新的PID空间，clone出的子进程会变成1号进程
	- ``CLONE_NEWIPC`` 子进程位于新的IPC命名空间中。这样SYSTEM V的IPC对象和POSIX的消息队列看上去会独立于原系统。
	- ``CLONE_NEWNS``  子进程会有新的挂载空间。
	- ``CLONE_NEWNET`` 如果配置文件中有关于网络的配置，则会增加该flag。它使得子进程有了新的网络设备的命名空间
1. 调用pin_rootfs。如果container的根文件系统是一个目录(而非独立的块设备)，则在container的根文件系统之外以可写权限打开一个文件。这样可以防止container在执行过程中将整个文件系统变成只读(原因很简单，因为已经有其他进程以读写模式打开一个文件了，所以设备是“可写忙”的。所以其他进程不能将文件系统重新挂载成只读)。
1. 调用lxc_clone，在新的命名空间中创建新的进程。
1. 父子进程协同工作，完成container的相关配置。

我们先来看一下lxc_clone是如何创建新的进程的。

#### lxc_clone
该函数的原型如下：

    pid_t lxc_clone(int (*fn)(void *), void *arg, int flags)

三个参数的含义如下：
    
    fn: 子进程要执行的函数入口
    arg：fn的输入参数
    flags: clone的flags

``lxc_clone``为clone api做了一个简单的封装，最后结果就是子进程会执行fn(arg)。在``lxc_spawn``处，``lxc_clone``是这样调用的：
    
    handler->pid = lxc_clone(do_start, handler, handler->clone_flags)

所以lxc_clone执行完后，handler的pid字段会保留子进程的pid(注意不是“1”，是子进程调用getpid()会变成1)。父进程继续，子进程执行do_start。

#### 父子进程同步
##### 同步机制
进程间同步的函数实现在sync.c中，其实现机制的分析可以见**sync.c**模块。这里只列举用于同步的函数：

 - ``lxc_sync_barrier_parent/child(struct lxc_handler* handler, int sequence)`` 发送sequence给parent/child,同时等待parent/child发送sequence+1的消息过来。
 - ``lxc_sync_wait_parent/child(struct lxc_handler* handler, int sequence)`` 等待parent/child发送sequence的消息过来。

##### 同步完成配置的过程

1. 父进程lxc_clone结束后，开始等待子进程发送``LXC_SYNC_CONFIGURE``的消息过来。此时，执行do_start的子进程完成了四件事情：
    1. 将信号处理表置为正常。
    1. 通过prctl api，将子进程设置为“如果父进程退出，则子进程收到SIGKILL的消息”。
    1. 关闭不需要的file handler
    1. 发送``LXC_SYNC_CONFIGURE``给父进程，通知父进程可以开始配置。同时等待父进程发送配置完成的消息``LXC_SYNC_POST_CONFIGURE``
1. 受到子进程发送的``LXC_SYNC_CONFIGURE``的消息后，父进程继续执行。父进程执行的动作如下：
    1. 调用lxc_cgroup_path_create创建新的cgroup
    2. 调用lxc_cgroup_enter将子进程加入到新的cgroup中。
    3. 如果有新的网络命名空间，则调用lxc_assign_network为之分配设备
    4. 如果有新的用户空间，如果配置了用户ids(包括uid，gid)映射，则做用户ids映射。该映射将container的id映射到了真正系统中一个不存在的id上，使得container可以在一个虚拟的id空间中做诸如“切换到root”之类的事情。详细讨论可参见模块**相关配置**。
    5. 发送``LXC_SYNC_POST_CONFIGURE``给子进程，并等待子进程发送``LXC_SYNC_CGROUP``的消息
1. 子进程收到``LXC_SYNC_POST_CONFIGURE``的消息被唤醒。完成如下动作：
    1. 如果id已被映射，则切换到root
    2. 开始container的设置，调用lxc_setup。主要有utsname、ip、根文件系统、设备挂载、console和tty等终端设备的各个方面的配置。
    3. 发送``LXC_SYNC_CGROUP``给父进程。并等待父进程发送``LXC_SYNC_CGROUP_POST``消息。
1. 父进程被唤醒。根据配置文件中对CGROUP的相关配置，调用setup_cgroup进行cgroup的设置。然后发送``LXC_SYNC_CGROUP_POST``给子进程。等待子进程发送``LXC_SYNC_CGROUP_POST+1``。
1. 子进程被唤醒。调用handler->ops->start函数。实际上是完成了对start.c中start函数的调用。该函数功能简单，基本就是通过exec执行了container的init程序，默认情况下为/sbin/init.
1. 子进程并没有给父进程返回``LXC_SYNC_CGROUP_POST+1``的消息，而是关掉了父子进程间的通信信道。这导致父进程被唤醒。被唤醒后，父进程完成了以下动作：
    1. 调用detect_shared_rootfs, 检测是否共享根文件系统，是的话卸载。
    2. 修改子进程tty文件的用户ids
    3. 执行handler->ops->post_start, 打印"XXX is started with pid XXX"字样。

#### 相关配置
在这一部分中，我们针对前面讲的父子进程的同步配置过程来对部分重要的函数做分析。

##### lxc_cgroup_path_create和lxc_cgroup_enter
函数定义在cgroup.c中。原型如下：
    
    char* lxc_cgroup_path_create(const char* lxcgroup, const char* name)
    int lxc_cgroup_enter(const char* cgpath, pid_t pid)
    
lxc_cgroup_path_create函数的作用是在cgroup各个已挂载使用的子系统的挂载点上为新创建的container新建一个文件夹。lxc_cgroup_enter的作用是把新创建的container加入到group cgpath中。

下面我们来举例说明：
比如挂载的子系统有blkio和cpuset，他们的挂载点分别是/cgroup/blkio和/cgroup/cpuset。

lxc_cgroup_path_create函数运行结束后，则会多出两个目录/cgroup/blkio/lxcgroup/name和/cgroup/cpuset/lxcgroup/name。如果传入参数lxcgroup为空，则会使用“lxc”。函数的返回值是新创建目录的相对路径。即“lxcgroup/name”。

lxc_cgroup_enter函数结束后，进程号"pid"会被追加到文件/cgroup/blkio/lxcgroup/name/tasks和/cgrop/cpuset/lxcgroup/name/tasks中。在lxc_spawn中，pid的实参用的是handler->pid，即clone出的子进程的id。

通过查看/proc/mounts查看cgroup的挂载点。通过查看/proc/cgroups查看正挂载使用的子系统。

##### id映射
查看confile.c下的config_idmap函数，可知在container配置文件中可以通过lxc.id_map来设置id映射。格式如下：

	lxc.id_map = u/g id_inside_ns id_outside_ns range

其中，u/g指定了是uid还是gid。后三个选项表示container中的[id_inside_ns, id_inside_ns+range)会被映射到真实系统中的
[id_outside_ns, id_outside_ns+range)。

在config_idmap执行后，配置文件中的配置条目被作为链表存放到conf->id_map字段下。在lxc_spawn中，通过调用lxc_map_ids函数来完成配置。

lxc_map_ids的实现在conf.c中，原型如下：
	
	int lxc_map_ids(struct lxc_list *idmap, pid_t pid)

第一个参数idmap为配置信息的链表，pid为新clone出的子进程的pid。lxc_map_ids的基本过程比较简单，就是将以u开头的配置项写入到文件/proc/pid/uid_map中，将以g开头的配置项写入到文件/proc/pid/gid_map中。

id映射是clone在flag CLONE_NEWUSER时指定的一个namespace特性。有关id映射可以参见[此处](http://lwn.net/Articles/532593/)。

##### lxc_setup
子进程do_start中调用的lxc_setup是一个非常重要的函数。container里面的很多配置都是在lxc_setup中完成的。这里重点分析setup_console和setup_tty两个函数，来查看比较困扰的终端字符设备是如何虚拟的。

setup_console的实现在conf.c中，函数原型如下：

	int setup_console(const struct lxc_rootfs *rootfs, const struct lxc_console *console, 
			char *ttydir)

rootf变量描述了container根文件系统的路径和挂载点。console变量描述了container的console设备的相关信息。在do_start的调用中，传来的实参是lxc_conf->console,这个字段是我们在lxc_init时初始化的。回顾当时的初始化过程：

 - console->slave和console->master分别存储了新分配的pty的slave和master的句柄。
 - console->peer存储了打开原系统"/dev/tty"的句柄。
 - console->name指向了新分配pty的文件路径

setup_console根据ttydir的值，分支调用了setup_dev_console或者setup_ttydir_console。我们只看setup_dev_console来了解原理。

在setup_dev_console中，主要动作就是将console->name指向的pty通过BIND的方式挂载到rootfs/dev/console文件中。可以看出，我们对container /dev/console的访问，实质上是对新分配pty的访问。

setup_tty的过程与此类似，在rootfs/dev/目录下创建tty1, tty2等常规文件，然后用BIND的方式将新创建的pty挂载到其上。

##### setup_cgroup
显然，container无法访问原来的cgroup根文件系统，所以这个任务只能由父进程在lxc_spawn中调用。该函数实现比较简单，根据config文件中的配置条目，将对应的value值写入到对应的cgroup文件中。

#### 剩下的事情
主进程陷入等待。子进程开始运行。

