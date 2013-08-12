---
layout: post
title: "Android init report 3"
description: ""
category: 
tags: []
---
{% include JB/setup %}
#/init第三、四部分详细分析

本文一定要在详细阅读了，系列的第二篇文章时候，再来阅读。  

`/init`程序第三部分

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

以上就是`/init`的第三部分，简单说就是把在`/init.rc`中解析到的**Action**，通过**trigger**挂载到全局变量`action_queue`中。`action_queue`其实就是一个等待被执行的**Action**队列。

那么我们来分析用到的函数`action_for_each_trigger`和`queue_builtin_action`

####函数`action_for_each_trigger`(/system/core/init/init_parser.c)

	void action_for_each_trigger(const char *trigger,
	                             void (*func)(struct action *act))
	{
	    struct listnode *node;
	    struct action *act;
	    list_for_each(node, &action_list) {
	        act = node_to_item(node, struct action, alist);
	        if (!strcmp(act->name, trigger)) {
	            func(act);
	        }
	    }
	}

我们通过上一篇文章的分析知道，**Action**的`name`就是**Trigger**的名字。由于要分析不只一个文件，所以不同的**Action**可以有相同的名字也就是相同**Trigger**[^trigger]。  

例如`/init.rc`和`/init.trace.rc`都有`boot`这个**Trigger**。

多个`action_for_each_trigger`，只用过一种`func`参数就是`action_add_queue_tail`:

	void action_add_queue_tail(struct action *act)
	{
	    list_add_tail(&action_queue, &act->qlist);
	}

函数很简单，就是把指定的**Action**挂到`action_queue`的尾部。注意，此时该**Action**还在`action_list`中的。
####函数`queue_builtin_action`(/system/core/init/init_parser.c)

	void queue_builtin_action(int (*func)(int nargs, char **args), char *name)
	{
	    struct action *act;
	    struct command *cmd;
	
	    act = calloc(1, sizeof(*act));
	    act->name = name;
	    list_init(&act->commands);
	
	    cmd = calloc(1, sizeof(*cmd));
	    cmd->func = func;
	    cmd->args[0] = name;
	    list_add_tail(&act->commands, &cmd->clist);
	
	    list_add_tail(&action_list, &act->alist);
	    action_add_queue_tail(act);
	}

该函数就是把一些**builtin action**（这些action不在rc文件中，是系统内置的），同时挂载到`action_list`和`action_queue`中。这些**Action**的**Command**只有一个就是传入的第一个参数。
系统的**builtin action**

    wait_for_coldboot_done_action
系统执行的第一个服务是`ueventd`用于检测并挂载设备。有些设备在内核加载时同时加载了，所以需要内核重新发送`uevent`事件向`ueventd`服务注册，称为`coldboot`。该**Action**通过`wait_for_file`函数等待`coldboot`完成（coldboot完成是`ueventd`会创健`coldboot_done`文件）。

    keychord_init_action

初始化keychord，一些服务可以通过keychord开启

    console_init_action

查看`/dev/console`是否能读写，并调用`load_565rle_image`加载开机动画。

    property_service_init_action

启动`Property Service`在第一部分的初始化中完成的只是在`/init`中的set和get。通过建立一个socket并监听来实现在全系统中的set和get功能。（主要调用`/system/core/init/property_service.c`中的`start_property_service`函数）

    signal_init_action

建立新的signal handler处理SIGCHLD信号，目的是在各个服务退出后进行相应的操作（因为服务都是`/init`的子进程所以是SIGCHLD）。

    check_startup_action

检查上面两个**Action**是否成功。

    queue_property_triggers_action

有些rc文件中的**Action**是以`on property：<name>=<value>`形式的。本**Action**的作用就是通过读取`Property System`检查这样的**Action**是否满足，是的话挂载到`action_queue`尾部。
`/init`程序第四部分

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
	
	        if (!action_queue_empty() || cur_action)
	            timeout = 0;
	
	#if BOOTCHART
	        if (bootchart_count > 0) {
	            if (timeout < 0 || timeout > BOOTCHART_POLLING_MS)
	                timeout = BOOTCHART_POLLING_MS;
	            if (bootchart_step() < 0 || --bootchart_count == 0) {
	                bootchart_finish();
	                bootchart_count = 0;
	            }
	        }
	#endif
	
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

函数`execute_one_command`

	void execute_one_command(void)
	{
	    int ret;
	
	    if (!cur_action || !cur_command || is_last_command(cur_action, cur_command)) {
	        cur_action = action_remove_queue_head();
	        cur_command = NULL;
	        if (!cur_action)
	            return;
	        INFO("processing action %p (%s)\n", cur_action, cur_action->name);
	        cur_command = get_first_command(cur_action);
	    } else {
	        cur_command = get_next_command(cur_action, cur_command);
	    }
	
	    if (!cur_command)
	        return;
	
	    ret = cur_command->func(cur_command->nargs, cur_command->args);
	    INFO("command '%s' r=%d\n", cur_command->args[0], ret);
	}

该函数就是不断执行`action_queue`中**Action**的**Command**。  

函数`restart_processes`

	static void restart_processes()
	{
	    process_needs_restart = 0;
	    service_for_each_flags(SVC_RESTARTING,
	                           restart_service_if_needed);
	}

函数`restart_service_if_needed`

	static void restart_service_if_needed(struct service *svc)
	{
	    time_t next_start_time = svc->time_started + 5;
	
	    if (next_start_time <= gettime()) {
	        svc->flags &= (~SVC_RESTARTING);
	        service_start(svc, NULL);
	        return;
	    }
	
	    if ((next_start_time < process_needs_restart) ||
	        (process_needs_restart == 0)) {
	        process_needs_restart = next_start_time;
	    }
	}

该函数比较难理解，其实是执行了如下的功能：

 - 服务的重启间隔是5秒，如果需要重启的服务启动超过5秒就需要重启。
 - 把全局变量`process_need_restart`的值设置成所有需要重启的服务的最近的重启时间。

在**Android**系统中由于文件在`fork`是继承的，往往`/init`和子进程——服务之间的通讯可以通过操作文件实现：

    某个服务向要向`/init`通讯，只要操作相应的继承过来的的文件。而`/init`通过`poll`轮询这些文件。一旦文件被操作时，`/init`就可以知道，从而调用相应的处理函数。

`/init`中有三个这样重要的文件：

    property_set_fd

用于监听property set事件

    signal_fd

用于监听服务的退出事件

	keychord_fd
用于监听keychord事件

把这三个文件描述符放到`ufds`中，通过`poll`[^poll]函数轮询对这三个文件的操作事件，分别执行

    handle_property_set_fd();

处理property set事件

    handle_keychord();

处理keychord事件

    handle_signal();
处理服务子信号（SIGCHLD）事件

我们只重点分析一下`handle_signal`函数：

	void handle_signal(void)
	{
	    char tmp[32];
	
	    /* we got a SIGCHLD - reap and restart as needed */
	    read(signal_recv_fd, tmp, sizeof(tmp));
	    while (!wait_for_one_process(0))
	        ;
	}

该函数调用`wait_for_process`

	static int wait_for_one_process(int block)
	{
	    pid_t pid;
	    int status;
	    struct service *svc;
	    struct socketinfo *si;
	    time_t now;
	    struct listnode *node;
	    struct command *cmd;
	
	    while ( (pid = waitpid(-1, &status, block ? 0 : WNOHANG)) == -1 && errno == EINTR );
	    if (pid <= 0) return -1;
	    INFO("waitpid returned pid %d, status = %08x\n", pid, status);
	
	    svc = service_find_by_pid(pid);
	    if (!svc) {
	        ERROR("untracked pid %d exited\n", pid);
	        return 0;
	    }
	
	    NOTICE("process '%s', pid %d exited\n", svc->name, pid);
	
	    if (!(svc->flags & SVC_ONESHOT)) {
	        kill(-pid, SIGKILL);
	        NOTICE("process '%s' killing any children in process group\n", svc->name);
	    }
	
	    /* remove any sockets we may have created */
	    for (si = svc->sockets; si; si = si->next) {
	        char tmp[128];
	        snprintf(tmp, sizeof(tmp), ANDROID_SOCKET_DIR"/%s", si->name);
	        unlink(tmp);
	    }
	
	    svc->pid = 0;
	    svc->flags &= (~SVC_RUNNING);
	
	        /* oneshot processes go into the disabled state on exit */
	    if (svc->flags & SVC_ONESHOT) {
	        svc->flags |= SVC_DISABLED;
	    }
	
	        /* disabled and reset processes do not get restarted automatically */
	    if (svc->flags & (SVC_DISABLED | SVC_RESET) )  {
	        notify_service_state(svc->name, "stopped");
	        return 0;
	    }
	
	    now = gettime();
	    if (svc->flags & SVC_CRITICAL) {
	        if (svc->time_crashed + CRITICAL_CRASH_WINDOW >= now) {
	            if (++svc->nr_crashed > CRITICAL_CRASH_THRESHOLD) {
	                ERROR("critical process '%s' exited %d times in %d minutes; "
	                      "rebooting into recovery mode\n", svc->name,
	                      CRITICAL_CRASH_THRESHOLD, CRITICAL_CRASH_WINDOW / 60);
	                android_reboot(ANDROID_RB_RESTART2, 0, "recovery");
	                return 0;
	            }
	        } else {
	            svc->time_crashed = now;
	            svc->nr_crashed = 1;
	        }
	    }
	
	    svc->flags |= SVC_RESTARTING;
	
	    /* Execute all onrestart commands for this service. */
	    list_for_each(node, &svc->onrestart.commands) {
	        cmd = node_to_item(node, struct command, clist);
	        cmd->func(cmd->nargs, cmd->args);
	    }
	    notify_service_state(svc->name, "restarting");
	    return 0;
	}

该函数功能如下：

- 通过`waitpid`函数获取退出的子服务的pid。如果服务是onshot的直接kill掉，否则就要标记成重启状态。

    svc->flags |= SVC_RESTARTING;

- 关闭该服务的socket

- 如果是critical的服务在一定时间内退出超过4次，就调用`reboot_android`进入recovery mode。

- 在服务重启之前执行Onrestart上的命令。

值得注意的是服务没有在此函数中真正重启，只是设置成SVC_RESTARTING。  

真正的重启是在上面分析的`restart_processes`中通过调用`service_start`完成。

[^trigger]:注意与此不同的不能有相同的**Service**名，否则会被直接忽略的。

[^poll]:`poll`的最后一个参数指定超时时间，该是通过process_need_restart计算的，其实就是现在到最近要重启服务的重启时间。这样超过该时间后，`poll`会直接返回从而不影响服务的重启。





