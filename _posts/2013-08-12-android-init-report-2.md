---
layout: post
title: "Android init report 2"
description: ""
category: 
tags: []
---
{% include JB/setup %}
#Android init.rc分析#
##1 前言
什么是init.rc文件？  

	import /init.usb.rc
	import /init.${ro.hardware}.rc
	import /init.trace.rc
	
	on early-init
	    # Set init and its forked children's oom_adj.
	    write /proc/1/oom_adj -16
	
	    # Set the security context for the init process.
	    # This should occur before anything else (e.g. ueventd) is started.
	    setcon u:r:init:s0
	
	    start ueventd
	
	# create mountpoints
	    mkdir /mnt 0775 root system
	
	on init
	
	sysclktz 0
	
	loglevel 3
	
	......
	
	on fs
	# mount mtd partitions
	    # Mount /system rw first to give the filesystem a chance to save a checkpoint
	    mount yaffs2 mtd@system /system
	    mount yaffs2 mtd@system /system ro remount
	    mount yaffs2 mtd@userdata /data nosuid nodev
	    mount yaffs2 mtd@cache /cache nosuid nodev
	
	on post-fs
	    ......
	
	on post-fs-data
		......
	
	on boot
		.......
	on nonencrypted
	    class_start late_start
	
	on charger
	    class_start charger
	
	on property:vold.decrypt=trigger_reset_main
	    class_reset main
		......
	service servicemanager /system/bin/servicemanager
	    class core
	    user system
	    group system
	    critical
	    onrestart restart zygote
	    onrestart restart media
	    onrestart restart surfaceflinger
	    onrestart restart drm
	
	service vold /system/bin/vold
	    class core
	    socket vold stream 0660 root mount
	    ioprio be 2
	
	service netd /system/bin/netd
	    class main
	    socket netd stream 0660 root system
	    socket dnsproxyd stream 0660 root inet
	    socket mdns stream 0660 root system
	
	service debuggerd /system/bin/debuggerd
		......

上面的就是一个`init.rc`的片段。可以在**Android**源代码中找到，位置在`/system/core/rootdir/`  
`init.rc`是**Android**系统`/init`程序读取的初始化配置文件，用于启动**Android**中的各种服务，以及配置系统。
  
## 2 `init.rc`分析
文件使用的脚本格式被称作**“Android Init Language”(AIL)**。  
**AIL**的解析以由空格（Whitespace）分隔的**token**组成的行为基本单位，这些行由四种类型组成，——`Action`、`Command`、`Service`、`Option`。

如果一行最开始是__"#"__，那么这一行是注释。

在`/init`的`main`函数中如下调用函数解析该文件：

    INFO("reading config file\n");
    init_parse_config_file("/init.rc");

####函数`init_parse_config_file`(`/system/core/init/init_parser.c`)####

	int init_parse_config_file(const char *fn)
	{
	    char *data;
	    data = read_file(fn, 0);
	    if (!data) return -1;
	
	    parse_config(fn, data);
	    DUMP();
	    return 0;
	}


该函数过程如下：

 - 首先调用函数`read_file`(在`/system/core/init/util.c`中)，把`/init.rc`配置文件读到`data`[^data]变量中，同时确保文件以“\n \0”结尾 
 - 最后，也是最关键的部分，调用`parse_config`函数进行配置文件分析。  

为了更好的了解`/init.rc`的配置究竟是什么，我们必须仔细分析`parse_config`函数。
####函数`parse_config`(`/system/core/init/init_parser.c`)####

	static void parse_config(const char *fn, char *s)
	{
		struct parse_state state;
	    struct listnode import_list;
	    struct listnode *node;
	    char *args[INIT_PARSER_MAXARGS];//用于存储每一行的token字符
	    int nargs;
	
	    nargs = 0;
	    state.filename = fn;
	    state.line = 0;
	    state.ptr = s;
	    state.nexttoken = 0;
	    state.parse_line = parse_line_no_op;
	
	    list_init(&import_list);
	    state.priv = &import_list;
	
	    for (;;) {
	        switch (next_token(&state)) {
	        case T_EOF:
	            state.parse_line(&state, 0, 0);
	            goto parser_done;
	        case T_NEWLINE:
	            state.line++;
	            if (nargs) {
	                int kw = lookup_keyword(args[0]);
	                if (kw_is(kw, SECTION)) {
	                    state.parse_line(&state, 0, 0);
	                    parse_new_section(&state, kw, nargs, args);
	                } else {
	                    state.parse_line(&state, nargs, args);
	                }
	                nargs = 0;
	            }
	            break;
	        case T_TEXT:
	            if (nargs < INIT_PARSER_MAXARGS) {
	                args[nargs++] = state.text;
	            }
	            break;
	        }
	    }
	
	parser_done:
	    list_for_each(node, &import_list) {
	         struct import *import = node_to_item(node, struct import, list);
	         int ret;
	
	         INFO("importing '%s'", import->filename);
	         ret = init_parse_config_file(import->filename);
	  	......
	    }
	}

该函数有两个重要的数据结构  
`struct parse_state`定义（`/system/core/init/parser.h`）  

	struct parse_state
	{
	    char *ptr;//文本的指针
	    char *text;//指向解析的单个token
	    int line;//行号
	    int nexttoken;
	    void *context;//指向不同的数据结构，表示当前正在解析Action或者Service
		/*处理行的函数，可以证明init.rc的解析是以行为单位的*/
	    void (*parse_line)(struct parse_state *state, int nargs, char **args);
	    const char *filename;//当前的文件名
	    void *priv;
	};

有点编译原理基础的就会明白，这就是**parser**的状态。  
还有  
    
    char *args[INIT_PARSER_MAXARGS];  
    int nargs;

在以行单位的解析中，把每一行解析的**token**字符串指针存放在`args`字符指针数组中，把当前行中的**token**个数存放在`nargs`中。

在函数`parse_config`中通过`switch`结构进行状态的转换。各种状态如下。

|状态	| 解释 	|
|:-------|:-------|
|T_EOF	|代表文件的结束     	|
|T_NEWLINE|代表新的一行，所以需要解析当前行		|
|T_TEXT	|代表一个**token**，把指针放到对应的`args`，并更新`nargs`		|  

重点分析状态**T_NEWLINE**.

	 case T_NEWLINE:
	            state.line++;
	            if (nargs) {
	                int kw = lookup_keyword(args[0]);
	                if (kw_is(kw, SECTION)) {
	                    state.parse_line(&state, 0, 0);
	                    parse_new_section(&state, kw, nargs, args);
	                } else {
	                    state.parse_line(&state, nargs, args);
	                }
	                nargs = 0;
	            }
	            break;

首先通过`lookup_keyworkd`和`kw_is`函数，查找本行的第一个**token**是什么类型的，如果是**Section**,就调用`parse_new_section`,否则调用行处理函数。

疑问来了，`state.parse_line`不是在开始赋值为`parse_line_no_op`的空函数了吗？调用空函数有什么意义啊？  
其实，秘密就在`parse_new_section`函数中。我们一步一步来解释。
首先解决什么是`Section`,这就需要分析`lookup_keyword`和`kw_is`函数了。

	int lookup_keyword(const char *s)
	{
	    switch (*s++) {
	    case 'c':
	    if (!strcmp(s, "opy")) return K_copy;
	        if (!strcmp(s, "apability")) return K_capability;
	        if (!strcmp(s, "hdir")) return K_chdir;
	        if (!strcmp(s, "hroot")) return K_chroot;
			......
	        break;
	    case 'd':
	        if (!strcmp(s, "isabled")) return K_disabled;
	        if (!strcmp(s, "omainname")) return K_domainname;
	        break;
		.......
	 
	    return K_UNKNOWN;
	}

该函数根据字符串返回一一对应的枚举类型。`kw_is`是宏：  

    #define kw_is(kw, type) (keyword_info[kw].flags & (type))

`keyword_info`是全局变量定义如下：（`/system/core/init/keywords.h`）

	#define KEYWORD(symbol, flags, nargs, func) \
	    [ K_##symbol ] = { #symbol, func, nargs + 1, flags, },
	struct {
	    const char *name;
	    int (*func)(int nargs, char **args);
	    unsigned char nargs;
	    unsigned char flags;
	} keyword_info[KEYWORD_COUNT] = {
	    [ K_UNKNOWN ] = { "unknown", 0, 0, 0 },
	    KEYWORD(capability,  OPTION,  0, 0)
	    KEYWORD(chdir,       COMMAND, 1, do_chdir)
	    KEYWORD(chroot,      COMMAND, 1, do_chroot)
	    KEYWORD(class,       OPTION,  0, 0)
	    KEYWORD(class_start, COMMAND, 1, do_class_start)
	    KEYWORD(class_stop,  COMMAND, 1, do_class_stop)
	    KEYWORD(class_reset, COMMAND, 1, do_class_reset)
	    KEYWORD(console,     OPTION,  0, 0)
	    KEYWORD(critical,    OPTION,  0, 0)
	    KEYWORD(disabled,    OPTION,  0, 0)
	    KEYWORD(domainname,  COMMAND, 1, do_domainname)
	    KEYWORD(exec,        COMMAND, 1, do_exec)
	    KEYWORD(export,      COMMAND, 2, do_export)
	    KEYWORD(group,       OPTION,  0, 0)
	    KEYWORD(hostname,    COMMAND, 1, do_hostname)
	    KEYWORD(ifup,        COMMAND, 1, do_ifup)
	    KEYWORD(insmod,      COMMAND, 1, do_insmod)
	    KEYWORD(import,      SECTION, 1, 0)
	    KEYWORD(keycodes,    OPTION,  0, 0)
	    KEYWORD(mkdir,       COMMAND, 1, do_mkdir)
	    KEYWORD(mount_all,   COMMAND, 1, do_mount_all)
	    KEYWORD(mount,       COMMAND, 3, do_mount)
	    KEYWORD(on,          SECTION, 0, 0)
	    KEYWORD(oneshot,     OPTION,  0, 0)
	    KEYWORD(onrestart,   OPTION,  0, 0)
	    KEYWORD(restart,     COMMAND, 1, do_restart)
	    KEYWORD(restorecon,  COMMAND, 1, do_restorecon)
	    KEYWORD(rm,          COMMAND, 1, do_rm)
	    KEYWORD(rmdir,       COMMAND, 1, do_rmdir)
	    KEYWORD(seclabel,    OPTION,  0, 0)
	    KEYWORD(service,     SECTION, 0, 0)
	    KEYWORD(setcon,      COMMAND, 1, do_setcon)
	    KEYWORD(setenforce,  COMMAND, 1, do_setenforce)
	    KEYWORD(setenv,      OPTION,  2, 0)
	    KEYWORD(setkey,      COMMAND, 0, do_setkey)
	    KEYWORD(setprop,     COMMAND, 2, do_setprop)
	    KEYWORD(setrlimit,   COMMAND, 3, do_setrlimit)
	    KEYWORD(setsebool,   COMMAND, 1, do_setsebool)
	    KEYWORD(socket,      OPTION,  0, 0)
	    KEYWORD(start,       COMMAND, 1, do_start)
	    KEYWORD(stop,        COMMAND, 1, do_stop)
	    KEYWORD(trigger,     COMMAND, 1, do_trigger)
	    KEYWORD(symlink,     COMMAND, 1, do_symlink)
	    KEYWORD(sysclktz,    COMMAND, 1, do_sysclktz)
	    KEYWORD(user,        OPTION,  0, 0)
	    KEYWORD(wait,        COMMAND, 1, do_wait)
	    KEYWORD(write,       COMMAND, 2, do_write)
	    KEYWORD(copy,        COMMAND, 2, do_copy)
	    KEYWORD(chown,       COMMAND, 2, do_chown)
	    KEYWORD(chmod,       COMMAND, 2, do_chmod)
	    KEYWORD(loglevel,    COMMAND, 1, do_loglevel)
	    KEYWORD(load_persist_props,    COMMAND, 0, do_load_persist_props)
	    KEYWORD(ioprio,      OPTION,  0, 0)
	};

关键字`import`、`on`、`service`代表新的**Section**的开始。
所以`init.rc`文件的结构如下：

 - 最高层由**Section**组成，分为`trigger`、`import`、`service`，分别以`on`, `import`,`service`关键字开头。
 - `import`**Section**只有一行，至于载入其他rc文件
 - `trigger`**Section**由 **Command**组成。
 - `service`**Section**有 **Option**组成。

接下来我们直击核心函数`parse_new_section`

	void parse_new_section(struct parse_state *state, int kw,
	                       int nargs, char **args)
	{
	    printf("[ %s %s ]\n", args[0],
	           nargs > 1 ? args[1] : "");
	    switch(kw) {
	    case K_service:
	        state->context = parse_service(state, nargs, args);
	        if (state->context) {
	            state->parse_line = parse_line_service;
	            return;
	        }
	        break;
	    case K_on:
	        state->context = parse_action(state, nargs, args);
	        if (state->context) {
	            state->parse_line = parse_line_action;
	            return;
	        }
	        break;
	    case K_import:
	        parse_import(state, nargs, args);
	        break;
	    }
	    state->parse_line = parse_line_no_op;
	}

在该函数中可以明显看到**Section**的种类，以及`state.parse_line`被更改。接下来我们按**Section**种类，分三部分分析。  
但是在这之前先介绍三个数据结构： 

    static list_declare(service_list);
    static list_declare(action_list);
    static list_declare(action_queue);

这三个全局变量都是链表的表头，是`/init`对`/init.rc`解析所要操作的关键函数，也可以说是解析的目的所在。`service_list`代表解析得到的**Service**，`action_list`代表解析得到的**Action**，`action_queue`代表将要执行的**Action**队列。  
`/init`可以认为主要是做了如下工作：

 1. 解析`/init.rc`，把得到的**Action**和 **Service**连接到`action_list`和`service_list`中。
 2. 内部或者外部出发`trigger`把对应的**Action**连接到`action_queue`。
 3. 在`for`循环中依次执行`action_queue`队列中**Action**对应的**Command**。

####Section Serivice####

每个**Service**，由一个`struct service`数据结构代表，定义如下：

	struct service {
	        /* list of all services */
	    struct listnode slist;//连接到service_list
	
	    const char *name;
	    const char *classname;
	
	    unsigned flags;
	    pid_t pid;
	    time_t time_started;    /* time of last start */
	    time_t time_crashed;    /* first crash within inspection window */
	    int nr_crashed;         /* number of times crashed within window */
	
	    uid_t uid;
	    gid_t gid;
	    gid_t supp_gids[NR_SVC_SUPP_GIDS];
	    size_t nr_supp_gids;
	
	#ifdef HAVE_SELINUX
	    char *seclabel;
	#endif
	
	    struct socketinfo *sockets;
	    struct svcenvinfo *envvars;
	
	    struct action onrestart;  /* Actions to execute on restart. */
	
	    /* keycodes for triggering this service via /dev/keychord */
	    int *keycodes;
	    int nkeycodes;
	    int keychord_id;
	
	    int ioprio_class;
	    int ioprio_pri;
	
	    int nargs;
	    /* "MUST BE AT THE END OF THE STRUCT" */
	    char *args[1];
	}; /*     ^-------'args' MUST be at the end of thi

####函数`parse_service`(`/system/core/init/init_parser.c`)

	static void *parse_service(struct parse_state *state, int nargs, char **args)
	{
	    struct service *svc;
	    if (nargs < 3) {
	        parse_error(state, "services must have a name and a program\n");
	        return 0;
	    }
	    if (!valid_name(args[1])) {
	        parse_error(state, "invalid service name '%s'\n", args[1]);
	        return 0;
	    }
	
	    svc = service_find_by_name(args[1]);
	    if (svc) {
	        parse_error(state, "ignored duplicate definition of service '%s'\n", args[1]);
	        return 0;
	    }
	
	    nargs -= 2;
	    svc = calloc(1, sizeof(*svc) + sizeof(char*) * nargs);
	    if (!svc) {
	        parse_error(state, "out of memory\n");
	        return 0;
	    }
	    svc->name = args[1];
	    svc->classname = "default";
	    memcpy(svc->args, args + 2, sizeof(char*) * nargs);
	    svc->args[nargs] = 0;
	    svc->nargs = nargs;
	    svc->onrestart.name = "onrestart";
	    list_init(&svc->onrestart.commands);
	    list_add_tail(&service_list, &svc->slist);
	    return svc;
	}

首先本**Section**的第一行必须是如下格式  

    service <service name> <program name>

而且在`valid_name`函数中规定，**service name**必须不超过16个字符，而且只能由字母、数字、“-”、“_”组成。  

当出现重名的**service**时，会被忽略。  

最后把**Service**挂到`service_list`尾部  

下面分析`parse_line_service`函数


	static void parse_line_service(struct parse_state *state, int nargs, char **args)
	{
	    struct service *svc = state->context;
	    struct command *cmd;
	    int i, kw, kw_nargs;
	
	    if (nargs == 0) {
	        return;
	    }
	
	    svc->ioprio_class = IoSchedClass_NONE;
	
	    kw = lookup_keyword(args[0]);
	    switch (kw) {
	    case K_capability:
	        break;
	    case K_class:
	        if (nargs != 2) {
	            parse_error(state, "class option requires a classname\n");
	        } else {
	            svc->classname = args[1];
	        }
	        break;
	    case K_console:
	        svc->flags |= SVC_CONSOLE;
	        break;
	    case K_disabled:
	        svc->flags |= SVC_DISABLED;
	        svc->flags |= SVC_RC_DISABLED;
	        break;
	    case K_ioprio:
	        if (nargs != 3) {
	            parse_error(state, "ioprio optin usage: ioprio <rt|be|idle> <ioprio 0-7>\n");
	        } else {
	            svc->ioprio_pri = strtoul(args[2], 0, 8);
	
	            if (svc->ioprio_pri < 0 || svc->ioprio_pri > 7) {
	                parse_error(state, "priority value must be range 0 - 7\n");
	                break;
	            }
	
	            if (!strcmp(args[1], "rt")) {
	                svc->ioprio_class = IoSchedClass_RT;
	            } else if (!strcmp(args[1], "be")) {
	                svc->ioprio_class = IoSchedClass_BE;
	            } else if (!strcmp(args[1], "idle")) {
	                svc->ioprio_class = IoSchedClass_IDLE;
	            } else {
	                parse_error(state, "ioprio option usage: ioprio <rt|be|idle> <0-7>\n");
	            }
	        }
	        break;
	    case K_group:
	        if (nargs < 2) {
	            parse_error(state, "group option requires a group id\n");
	        } else if (nargs > NR_SVC_SUPP_GIDS + 2) {
	            parse_error(state, "group option accepts at most %d supp. groups\n",
	                        NR_SVC_SUPP_GIDS);
	        } else {
	            int n;
	            svc->gid = decode_uid(args[1]);
	            for (n = 2; n < nargs; n++) {
	                svc->supp_gids[n-2] = decode_uid(args[n]);
	            }
	            svc->nr_supp_gids = n - 2;
	        }
	        break;
	    case K_keycodes:
	        if (nargs < 2) {
	            parse_error(state, "keycodes option requires atleast one keycode\n");
	        } else {
	            svc->keycodes = malloc((nargs - 1) * sizeof(svc->keycodes[0]));
	            if (!svc->keycodes) {
	                parse_error(state, "could not allocate keycodes\n");
	            } else {
	                svc->nkeycodes = nargs - 1;
	                for (i = 1; i < nargs; i++) {
	                    svc->keycodes[i - 1] = atoi(args[i]);
	                }
	            }
	        }
	        break;
	    case K_oneshot:
	        svc->flags |= SVC_ONESHOT;
	        break;
	    case K_onrestart:
	        nargs--;
	        args++;
	        kw = lookup_keyword(args[0]);
	        if (!kw_is(kw, COMMAND)) {
	            parse_error(state, "invalid command '%s'\n", args[0]);
	            break;
	        }
	        kw_nargs = kw_nargs(kw);
	        if (nargs < kw_nargs) {
	            parse_error(state, "%s requires %d %s\n", args[0], kw_nargs - 1,
	                kw_nargs > 2 ? "arguments" : "argument");
	            break;
	        }
	
	        cmd = malloc(sizeof(*cmd) + sizeof(char*) * nargs);
	        cmd->func = kw_func(kw);
	        cmd->nargs = nargs;
	        memcpy(cmd->args, args, sizeof(char*) * nargs);
	        list_add_tail(&svc->onrestart.commands, &cmd->clist);
	        break;
	    case K_critical:
	        svc->flags |= SVC_CRITICAL;
	        break;
	    case K_setenv: { /* name value */
	        struct svcenvinfo *ei;
	        if (nargs < 2) {
	            parse_error(state, "setenv option requires name and value arguments\n");
	            break;
	        }
	        ei = calloc(1, sizeof(*ei));
	        if (!ei) {
	            parse_error(state, "out of memory\n");
	            break;
	        }
	        ei->name = args[1];
	        ei->value = args[2];
	        ei->next = svc->envvars;
	        svc->envvars = ei;
	        break;
	    }
	    case K_socket: {/* name type perm [ uid gid ] */
	        struct socketinfo *si;
	        if (nargs < 4) {
	            parse_error(state, "socket option requires name, type, perm arguments\n");
	            break;
	        }
	        if (strcmp(args[2],"dgram") && strcmp(args[2],"stream")
	                && strcmp(args[2],"seqpacket")) {
	            parse_error(state, "socket type must be 'dgram', 'stream' or 'seqpacket'\n");
	            break;
	        }
	        si = calloc(1, sizeof(*si));
	        if (!si) {
	            parse_error(state, "out of memory\n");
	            break;
	        }
	        si->name = args[1];
	        si->type = args[2];
	        si->perm = strtoul(args[3], 0, 8);
	        if (nargs > 4)
	            si->uid = decode_uid(args[4]);
	        if (nargs > 5)
	            si->gid = decode_uid(args[5]);
	        si->next = svc->sockets;
	        svc->sockets = si;
	        break;
	    }
	    case K_user:
	        if (nargs != 2) {
	            parse_error(state, "user option requires a user id\n");
	        } else {
	            svc->uid = decode_uid(args[1]);
	        }
	        break;
	    case K_seclabel:
	#ifdef HAVE_SELINUX
	        if (nargs != 2) {
	            parse_error(state, "seclabel option requires a label string\n");
	        } else {
	            svc->seclabel = args[1];
	        }
	#endif
	        break;
	
	    default:
	        parse_error(state, "invalid option '%s'\n", args[0]);
	    }
	}

该函数就是对**Service**的**Option**进行解析，并把相应的**struct service**的字段赋值。  

**Services**的**Option**是服务的修饰符，可以影响服务如何以及怎样运行。服务支持的选项如下：

    1. critical 

表明这是一个非常重要的服务。如果该服务4分钟内退出大于4次，系统将会重启并进入 Recovery （恢复）模式。

    2. disabled

表明这个服务不会同与他同trigger （触发器）下的服务自动启动。该服务必须被明确的按名启动。必须通过`start <service name>`**Command**,`class_start <class_name>`**Command**不能启动即使该服务在

    3.  setenv <name> <value>

在进程启动时将环境变量<name>设置为<value>。

    4.  socket <name> <type> <perm> [ <user> [ <group> ] ]

   创建一个unix域的名为/dev/socket/<name> 的套接字，并传递它的文件描述符给已启动的进程。<type> 必须是 "dgram","stream" 或"seqpacket"。用户和组默认是0。

    5.  user <username>

在启动这个服务前改变该服务的用户名。此时默认为 root。

    6.  group <groupname> [<groupname> ]*

在启动这个服务前改变该服务的组名。除了（必需的）第一个组名，附加的组名通常被用于设置进程的补充组（通过setgroups函数），档案默认是root。

    7.  oneshot

   服务退出时不重启。

    8.  class <name>

   指定一个服务类。所有同一类的服务可以同时启动和停止。如果不通过class选项指定一个类，则默认为"default"类服务。

    9. onrestart

当服务重启，执行一个命令。

####Section Action####
每个**Action**以及包含的**Command**由如下数据结构表示：

	struct command
	{
	        /* list of commands in an action */
	    struct listnode clist;
	
	    int (*func)(int nargs, char **args);
	    int nargs;
	    char *args[1];
	};
	
	struct action {
	        /* node in list of all actions */
	    struct listnode alist;//连接到action_list
	        /* node in the queue of pending actions */
	    struct listnode qlist;//连接到action_queue
	        /* node in list of actions for a trigger */
	    struct listnode tlist;
	
	    unsigned hash;
	    const char *name;
	
	    struct listnode commands;//包含command的链表表头
	    struct command *current;
	};

####函数`parse_action`(`/system/core/init/init_parser.c`)

	static void *parse_action(struct parse_state *state, int nargs, char **args)
	{
	    struct action *act;
	    if (nargs < 2) {
	        parse_error(state, "actions must have a trigger\n");
	        return 0;
	    }
	    if (nargs > 2) {
	        parse_error(state, "actions may not have extra parameters\n");
	        return 0;
	    }
	    act = calloc(1, sizeof(*act));
	    act->name = args[1];
	    list_init(&act->commands);
	    list_add_tail(&action_list, &act->alist);
	        /* XXX add to hash */
	    return act;
	}

首先本**Section**的第一行必须是如下格式  

    on <trigger name>

最后把**Action**挂到`action_list`尾部。可以看到似乎打算把**Action**加到hash表中但是还没有实现。

下面分析`parse_line_action`函数

	static void parse_line_action(struct parse_state* state, int nargs, char **args)
	{
	    struct command *cmd;
	    struct action *act = state->context;
	    int (*func)(int nargs, char **args);
	    int kw, n;
	
	    if (nargs == 0) {
	        return;
	    }
	
	    kw = lookup_keyword(args[0]);
	    if (!kw_is(kw, COMMAND)) {
	        parse_error(state, "invalid command '%s'\n", args[0]);
	        return;
	    }
	
	    n = kw_nargs(kw);
	    if (nargs < n) {
	        parse_error(state, "%s requires %d %s\n", args[0], n - 1,
	            n > 2 ? "arguments" : "argument");
	        return;
	    }
	    cmd = malloc(sizeof(*cmd) + sizeof(char*) * nargs);
	    cmd->func = kw_func(kw);
	    cmd->nargs = nargs;
	    memcpy(cmd->args, args, sizeof(char*) * nargs);
	    list_add_tail(&act->commands, &cmd->clist);
	}


Actions后需要跟若干个命令，这些命令如下：

    1.  exec <path> [<argument> ]*

创建和执行一个程序（`<path>`）。在程序完全执行前，init将会阻塞。由于它不是内置命令，应尽量避免使用exec ，它可能会引起init执行超时。

    2.  export <name> <value>

在全局环境中将`<name>`变量的值设为`<value>`。（这将会被所有在这命令之后运行的进程所继承）

    3.  ifup <interface>

启动网络接口

    4.  import <filename>

指定要解析的其他配置文件。常被用于当前配置文件的扩展

    5.  hostname <name>

设置主机名

    6.  chdir <directory>

改变工作目录

    7.  chmod <octal-mode><path>

改变文件的访问权限

    8.  chown <owner><group> <path>

更改文件的所有者和组

    9.  chroot <directory>

  改变处理根目录

    10.  class_start<serviceclass>

   启动所有指定服务类下的未运行服务。

    11  class_stop<serviceclass>

  停止指定服务类下的所有已运行的服务。

    12.  domainname <name>

   设置域名

    13.  insmod <path>

   加载path指定的驱动模块

    14.  mkdir <path> [mode][owner] [group]

   创建一个目录`<path>` ，可以选择性地指定mode、owner以及group。如果没有指定，默认的权限为755，并属于root用户和 root组。

    15. mount <type> <device> <dir> [<mountoption> ]*

   试图在目录`<dir>`挂载指定的设备。`<device>` 可以是mtd@name的形式指定一个mtd块设备。`<mountoption>`包括 "ro"、"rw"、"re

    16.  setkey

   保留，暂时未用

    17.  setprop <name><value>

   将系统属性`<name>`的值设为`<value>`。

    18. setrlimit <resource> <cur> <max>

   设置`<resource>`的rlimit （资源限制）

    19.  start <service>

   启动指定服务（如果此服务还未运行）。

    20．stop<service>

   停止指定服务（如果此服务在运行中）。

    21. symlink <target> <path>

   创建一个指向`<path>`的软连接`<target>`。

    22. sysclktz <mins_west_of_gmt>

   设置系统时钟基准（0代表时钟滴答以格林威治平均时（GMT）为准）

    23.  trigger <event>

  触发一个事件。用于Action排队

    24.  wait <path> [<timeout> ]

等待一个文件是否存在，当文件存在时立即返回，或到<timeout>指定的超时时间后返回，如果不指定<timeout>，默认超时时间是5秒。

    25. write <path> <string> [ <string> ]*

向`<path>`指定的文件写入一个或多个字符串。  


####Section Import####
每个**Import**由如下数据结构表示：

	struct import {
	    struct listnode list;
	    const char *filename;
	};



	void parse_import(struct parse_state *state, int nargs, char **args)
	{
	    struct listnode *import_list = state->priv;
	    struct import *import;
	    char conf_file[PATH_MAX];
	    int ret;
	
	    if (nargs != 2) {
	        ERROR("single argument needed for import\n");
	        return;
	    }
	
	    ret = expand_props(conf_file, args[1], sizeof(conf_file));
	    if (ret) {
	        ERROR("error while handling import on line '%d' in '%s'\n",
	              state->line, state->filename);
	        return;
	    }
	
	    import = calloc(1, sizeof(struct import));
	    import->filename = strdup(conf_file);
	    list_add_tail(import_list, &import->list);
	    INFO("found import '%s', adding to import list", import->filename);
	}

函数`expand_props`把配置文件中的`${<property_name>}`，通过`Property System`读取对应的值。通常要读取`ro.machine`和`ro.arch`的值，展开后形成真正的文件名，然后挂载在`state.priv`上。

在`parse_config`函数的末尾，有如下代码：

	parser_done:
	    list_for_each(node, &import_list) {
	         struct import *import = node_to_item(node, struct import, list);
	         int ret;
	
	         INFO("importing '%s'", import->filename);
	         ret = init_parse_config_file(import->filename);

实现了对import进的文件的解析。

[^data]:不知为什么，`data`是通过`malloc`函数在堆上申请的，但在`parse_config`函数中没有释放，在`init_parse_config_file`中也没有释放。这不是内存泄漏吗？？

