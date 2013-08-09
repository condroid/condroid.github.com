---
layout: post
title: "Cgroup Research Report"
description: ""
category: 
tags: []
---
{% include JB/setup %}

Control Groups (Cgroups) 是 Red Hat Enterprise Linux 6 (以后简称 RHEL6) 提供的一项内核功能。Cgroup是将任意进程进行分组化管理的内核功能。  
Cgroup提供了一个cgroup虚拟文件系统，作为进行分组管理和各子系统设置的`用户接口`。因此，要使用cgroup，必须先挂载cgroup文件系统：

    mount -t cgroup -o 子系统名 cgroup /sys/fs/cgroup/子系统名
我们可以使用 Cgroups 为任务（进程）分配资源，例如 CPU 时间、系统内存、网络带宽等。我们可以对 Cgroups 进行监控，禁止 Cgroups 控制下的进程访问某些资源，还可以在一个运行中的系统中对 Cgroups 动态地进行配置。cgconfig ( control group config ) 是一项系统服务，它可以根据配置文件创建 Cgroups，我们可以通过它在每次重启操作系统之后保持一致的 Cgroups 配置。  

###Cgroup子系统
Cgroups 的组织结构为层次体系（目录树），Cgroups有多棵目录树，每棵树对应一个或多个子系统（一个子系统表示一个单一的资源）。目前Cgroups提供了9个子系统：

- blkio- 该子系统限制块设备的输入输出访问;
- cpu- 该子系统调度cgroup中进程的cpu访问;
- cpuacct- 该子系统生成cgroup中的任务使用cpu资源的报告;
- cpuset- 该子系统用于将cpu和内存节点指定给cgroup中的任务;
- devices- 该子系统用于限制cgroup中任务对设备的访问权限;
- freezer- 该子系统可以暂停和继续cgroup中的任务
- memory- 该子系统用于设定cgroup中任务使用的内存限额，并生成内存资源报告
- net_cls- network classifer cgroup使用等级标识符`classid`标记网络数据包
- net_prio- 该子系统可以动态设置每个网卡的优先级

###Cgroup层级关系
1. 一个层级结构可以关联一个或多个子系统
![](http://elmer-wordpress.stor.sinaapp.com/uploads/2012/11/RMG-rule1.png) 
  
1. 任何单个子系统不可以被关联到一个以上的层次结构，如果其中一个层次结构已经关系到一个不同的子系统。![](http://elmer-wordpress.stor.sinaapp.com/uploads/2012/11/RMG-rule2.png)  

1. 一个任务不能同时属于同一个层次结构中的两个 cgroup。
![](http://elmer-wordpress.stor.sinaapp.com/uploads/2012/11/RMG-rule3.png)  

1. 当 cgroups 中的一个任务 fork 出一个新任务时，新任务自动继承其父任务的 cgroup 关系。但是，新任务与父任务之间是完全独立的，新任务可以被移动到其他的 cgroups 。
![](http://elmer-wordpress.stor.sinaapp.com/uploads/2012/11/RMG-rule4.png)

###Cgroup创建层次结构实例
1. 首先创建一个目录，作为层次结构（目录树）的挂载点：

        mkdir /sys/fs/cgroup/cpu_and_mem
1. 接着挂载cgroup相应的子系统到该层次结构下：

        mount -t cgroup -o cpu,cpuset,memory cpu_and_mem /sys/fs/cgroup/cpu_and_mem
1. 使用lssubsys来查看当前已经挂载了的子系统：

        # lssubsys -am
        cpu,cpuset,memory /sys/fs/cgroup/cpu_and_mem
        blkio
        cpuacct
        devices
        freezer
1. 修改挂载的子系统，如现要将cpu_and_mem组也关联到cpuacct中：

        mount -t cgroup -o remount,cpu,cpuacct,cpuset,memory cpu_and_mem /sys/fs/cgroup/cpu_and_mem
1. 如果要删除一个层级结构（目录树），直接umount相应的挂载点：

        umount /sys/fs/cgroup/cpu_and_mem

###Cgroup创建进程组实例
上面，已经创建了一个层级结构，即进程组的父目录，接下来就可以在该结构下创建group了。  
1. 创建组
  
        mkdir /sys/fs/cgroup/cpu/lab1/group1
        mkdir /sys/fs/cgroup/cpuset/lab1/group1

1. tasks
此时，cpu/lab1/group1的目录里已经自动生成了许多文件，文件名前缀为cgroup的是由cgroup的基础结构提供的特殊文件;前缀为cpu的是由cpu子系统提供的特殊文件。在这些特殊的文件中，最重要的是`tasks`文件，其记录了属于这个分组的PID。
1. 分组
在cgroup文件系统中，一个目录就是一个分组。每个分组都是一系列线程的集合。cgroup/cpu, cgroup/blkio, cgroup/cpuset等等，这些目录是每个子系统的根目录，其tasks默认包含了当前系统所有进程的PID。*不过，当cpu,cpuset,blkio等目录下又有子目录时，子目录有自己的tasks，此时，父tasks会迁移一些进程到子tasks里去*









