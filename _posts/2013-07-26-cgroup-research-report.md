---
layout: post
title: "Cgroup Research Report"
description: ""
category: 
tags: []
---
{% include JB/setup %}

Cgroup Research Report
=========

Control Groups (Cgroups) 是 Red Hat Enterprise Linux 6 (以后简称 RHEL6) 提供的一项内核功能。Cgroup是将任意进程进行分组化管理的内核功能。  
Cgroup提供了一个cgroup虚拟文件系统，作为进行分组管理和各子系统设置的`用户接口`。因此，要使用cgroup，必须先挂载cgroup文件系统：

    mount -t cgroup -o 子系统名 层级名(目录名) /sys/fs/cgroup/层级名(目录名)
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
**/cgroup（或者/sys/fs/cgroup）目录下每个文件夹都是一个层级，其中cgroup/×××中的×××目录称为根层级。层级的名字可以随便起哦。通常的默认配置喜欢把子系统（如blkio）挂载到同名（如blkio）的层级上。其实根层级名不需要和子系统相同。也可以把多个子系统挂到一个层级上，但是一个子系统不能挂到多个层级上，会提示already mounted or busy**  
  
1. 一个层级结构可以关联一个或多个子系统（*结果是，**cpu**和 **memory**子系统都关附加到一个层级中*）  
![](http://elmer-wordpress.stor.sinaapp.com/uploads/2012/11/RMG-rule1.png) 
  
1. 任何单个子系统不可以被关联到一个以上的层次结构（*结果是，**cpu**子系统永远无法附加到两个不同的层级中*） 
![](http://elmer-wordpress.stor.sinaapp.com/uploads/2012/11/RMG-rule2.png)  

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
###Cgroup虚拟文件系统的挂载与卸载
1. 可以通过/proc/cgroups查看系统支持的cgroup子系统，其中hierarchy项为0表明该子系统尚未挂载，非0表示已经挂载。若hierarchy项值相同的子系统表明这些子系统对应到同一层级结构（同一目录）。
![](https://github.com/condroid/condroid.github.com/blob/master/imgs/Screenshot%20-%2008092013%20-%2008:19:57%20PM.png?raw=true)  

1. 可以使用lssubsys命令（libcgroup工具集）来更清晰的查看当前cgroup子系统的挂载情况和挂载点信息：
![](https://github.com/condroid/condroid.github.com/blob/master/imgs/20130809cgroup2.png?raw=true)<br/>
<br/>
![](https://github.com/condroid/condroid.github.com/blob/master/imgs/20130809cgroup3.png?raw=true)
<br/>
1. 卸载cgroup子系统  
（1）先把各子系统目录下的group依次从底层删除,使用`cgclear`命令（也属于libcgroup工具集）。  
（2）依次将lssubsys中的各个挂载点umount掉。  
（3）必须先删除再umount，否则如果直接umount虽然目录没有了，但其实并没有umount成功，通过/proc/cgroup可以看到它的hierarchy项非0。  
（4）如果没有umount成功，应该先再把该子系统mount到一个目录上，然后依次把没有rmdir的目录先全部rm了，再umount。
1. 挂载cgroup子系统
![](https://github.com/condroid/condroid.github.com/blob/master/imgs/20130809cgroup4.png?raw=true)  

1. 添加子目录
创建一个cgroup，在刚才mount的目录下：

        mkdir /cgroup/cgtest  
这样就创建了一个cgroup（该操作相对的是rmdir，即只有把该cgroup内的tasks移到top group才能真正将一个cgroup删除掉），此时可以看到新目录下已经有许多文件了。
###libcgroup工具
####libcgroup工具集安装
使用cgroup的最简单的方法是安装libcgroup工具集。虽然可以使用shell命令来挂载和设定cgroup。但是，使用libcgroup工具可简化过程并扩展功能。
redhat系：

    yum install libcgroup
debian系：

    sudo apt-get install cgroup-bin
cgroup服务的启动和停止（cgroup启动时会自动读取配置文件/etc/cgconfg.conf，根据其内容创建和挂载指定的cgroup子系统）：

    service cgconfig start|stop
####cgconfig配置文件分析
/etc/cgconfig.conf是cgroup配置工具libcgroup用来进行cgroup组的定义，参数设定以及挂载点定义的配置文件，主要由mount和group两个section构成。
1. mount section的语法格式如下：

    mount {
    <controller> = <path>;
    ...
    }
controller：内核子系统的名称  
path：该子系统的挂载点
  
举个列子：

    mount {
    cpuset = /cgroup/red;
    }
上面定义相当于如下shell指令：

    mkdir /cgroup/red
    mount -t cgroup -o cpuset red /cgroup/red
2. group section的格式如下：

    group <name> {
    [<permissions>]
    <controller> {
    <param name> = <param value>;
    …
    }
    …
    }
name: 指定cgroup的名称  
permissions：可选项，指定cgroup对应的挂载点文件系统的权限，root用户拥有所有权限。 
controller：子系统的名称  
param name 和 param value：子系统的属性及其属性值  
  
举个列子：

    group daemons/www { ## 定义daemons/www(web服务器进程)组
    perm { ## 定义这个组的权限
              task {
                     uid = root;
                     gid = webmaster;
                  }
              admin {
                    uid = root;
                    gid = root;
                   }
             }

      cpu { ## 定义cpu子系统的属性及其值，即属于词组的任务的权重为1000
             cpu.shares = 1000;
          }
     }
上面的配置文件相当于执行了如下的shell命令：

    mkdir /mnt/cgroups/cpu/daemons
    mkdir /mnt/cgroups/cpu/daemons/www
    chown root:root /mnt/cgroups/cpu/daemons/www/*
    chown root:webmaster /mnt/cgroups/cpu/daemons/www/tasks
    echo 1000 > /mnt/cgroups/cpu/daemons/www/cpu.shares
###Cgroup子系统介绍
####blkio
blkio子系统控制并监控cgroup中的任务对块设备的I/O访问。在部分这样的伪文件中写入值可限制访问或者带宽，且从这些伪文件中读取值可提供I/O操作信息。  
**blkio.weight:** 指定cgroup默认可用访问块I/O 的相对比例（加权），范围在100～1000。这个值可由具体设备的blkio.weight_device参数覆盖。  
举个列子：将cgroup访问块设备的默认加权设定为500

    echo 500 > blkio.weight
**blkio.weight_device:**指定对cgroup中可用的 **具体设备** I/O访问的相对比例（加权），范围是100～1000。这个值的格式为主设备号：从设备号 权值。  
举个例子：为访问/dev/sda的cgroup分配加权500

    echo 8:0 500 > blkio.weight_device
**blkio.time:**报告cgroup对具体设备的I/O访问时间。条目有三个字段主设备号：从设备号 时间（ms）

    echo 8:0 1500 > blkio.time
####CPU
CPU子系统调度对cgroup的CPU访问。可根据以下参数调度对CPU资源的访问，每个参数都独立存在于cgroup虚拟文件系统的伪文件中。  
**cpu.shares：**指定在cgroup中的进程可用的相对共享CPU时间的整数值。  
>举个例子：在两个cgroup中都将**cpu.shares**设定为1的任务将有相同的CPU时间，但在cgroup中将**cpu.shares**设定为2的任务可使用的CPU时间是在cgroup中将**cpu.shares**设定为1的任务可使用的CPU时间的两倍。  

**cpu.rt_runtime_us：**指定在某个时间段中cgroup中的任务对CPU资源的最长连续访问时间。这个属性是为了访问一个cgroup中的进程独占CPU时间。  
>举个例子：如果cgroup中的任务应该可以每5秒中有4秒时间访问CPU资源，需要将**cpu.rt_runtime_us**设定为4000000,并将**cpu.rt_period_us**设定为5000000。  

**cpu.rt_period_us：**配合上例使用，设定时间段的长度。
####cpuacct
CPU Accounting（cpuacct）子​​​系​​​统​​​自​​​动​​​生​​​成​​​ cgroup 中​​​任​​​务​​​所​​​使​​​用​​​的​​​ CPU 资​​​源​​​报​​​告​​​，其​​​中​​​包​​​括​​​子​​​组​​​群​​​中​​​的​​​任​​​务​​​。  
**cpuacct.stat:**报​​​告​​​这​​​个​​​ cgroup 及​​​其​​​子​​​组​​​群​​​中​​​的​​​任​​​务​​​使​​​用​​​用​​​户​​​模​​​式​​​和​​​系​​​统​​​（内​​​核​​​）模​​​式​​​消​​​耗​​​的​​​ CPU 循​​​环​​​数​​​（单​​​位​​​由​​​系​​​统​​​中​​​的​​​ USER_HZ 定​​​义​​​）。  

​​​ 
**cpuacct.usage:**报​​​告​​​这​​​个​​​ cgroup 中​​​所​​​有​​​任​​​务​​​（包​​​括​​​层​​​级​​​中​​​的​​​低​​​端​​​任​​​务​​​）消​​​耗​​​的​​​总​​​ CPU 时​​​间​​​（纳​​​秒​​​）。  
​​​ 

**cpuacct.usage_percpu:**报​​​告​​​这​​​个​​​ cgroup 中​​​所​​​有​​​任​​​务​​​（包​​​括​​​层​​​级​​​中​​​的​​​低​​​端​​​任​​​务​​​）在​​​每​​​个​​​ CPU 中​​​消​​​耗​​​的​​​ CPU 时​​​间​​​（以​​​纳​​​秒​​​为​​​单​​​位​​​）。

####cpuset
cpuset子系统为cgroup分配独立CPU和内存节点。可根据以下参数指定每个cpuset，每个参数都在控制组群虚拟文件系统中有单独的



























