<h1>OpenMATBC: An open-source version of the Multi-Attribute Task Battery (MATB) with Collaborative Support</h1>


<h2>Base OpenMATB</h2>

First presented at a NASA Technical memorandum (Comstock & Arnegard, 1992), the Multi-Attribute Task Battery (MATB) contained a set of interactive tasks that were representative of those performed in aircraft piloting. The MATB requires participants to engage in four tasks presented simultaneously on a computer screen. They consist of (1) a monitoring task, (2) a tracking task, (3) an auditory communication task, and (4) a resource management task. The display screen also encompasses a scheduling view (5) for displaying a chart of incoming task events

<center><img src="https://user-images.githubusercontent.com/10955668/49248376-d6ce3c80-f419-11e8-9416-7e0fe3e11d45.png" width=400></center>

As a great deal of time passed between iterations of the MATB implementation (Comstock & Arnegard, 1992), the makers of OpenMATB looked to address research requirements that were no longer satisfied. 
OpenMATB aimed to provide an open-source re-implementation of the multi-attribute task battery. It promoted three aspects: 
(1) tasks customization for full adaptation of the battery,
(2) software extendability to easily add new features, 
(3) experiment replicability to provide significant results.

Those aspects are detailed in: Cegarra, J., Valéry, B., Avril, E., Calmettes, C. & Navarro, J. (2020). OpenMATB: An open source implementation of the Multi-Attribute Task Battery. <i>Behavior Research Methods</i> https://doi.org/10.3758/s13428-020-01364-w

Note: Text of this section just minimally edited from the original OpenMATB README, which can be found <a href="https://github.com/juliencegarra/OpenMATB">here</a>.

<h2>OpenMATB Collaborative</h2>

This project is a fork of the original OpenMATB. It adds support for shared tasks between multiple participants, along with a number of other features. These features are outlined below.

<h3>Participant Interaction</h3>

Real world tasks frequently involve collaboration or competition between individuals. In the MATB context, the obvious example is the interaction between pilot and copilot. OpenMATBC adds twisted Perspective Broker networking to OpenMATB, enabling the state of MATB to be communicated between two computers, which in turn enables creation of arbitrary collaborative or competitive tasks. As a base line for this, all base MATB tasks now support syncronising their state between both machines and accepting input from either participant.

<h3>Collaborative Matching</h3>

One specific collaborative task is provided with this fork: the Collaborative Matching task. This task is a replacement for the standard Tracking task. Participants performing the collaborative matching task are presented with a window into a scene. This scene may be navigated with the joystick. There are various objects in the scene, one or more of which should appear in both participant's scene. Both participants must select an object of the same kind within a time limit to complete the task. For the remainder of the time limit (i.e. while participants are waiting for the next matching task) participants must keep their scene centered on the target object.

<h3>Scenario Command Priorities</h3>

Base OpenMATB scenarios require commands of the form "h:mm:ss;command". This is sufficient in many cases, but runs into some issues when you have many commands that need to be executed at the same second. It is sometimes important that these commands are executed in the correct order, but this is not easy to explicitly control with base OpenMATB. OpenMATBC adds priorities to commands. OpenMATB style commands function exactly as before, but now a priority may be added to any command, giving the form "h:mm:ss-p;command", where 'p' is priority. Commands with higher priority are executed before commands with lower priority.

<h3>Scenario Generation</h3>

OpenMATBC adds a scenario generator script. Base OpenMATB now also has a scenario generation feature, however the version this fork came from did not have such a feature so the two scripts are not related. The scenario generation script can be used to generate complex scenarios with many commands from only a short TOML file describing the scenario. These scenarios can be generated with any combination of the MATB tasks. Additionally, every task can be generated at any difficulty you specify. These scenarios can also be specified in terms of experimental blocks, and automatically include commands to add flags to the logs for when each of these blocks begin and end.

This system can help address one of the weaknesses of MATB as a research tool. Researchers have a great deal of flexibility to create whatever scenario they wish. This is valuable, but can make it quite difficult to compare the tasks given by researchers in two different pieces of research. If both of those researchers used the scenario generator to create scenarios with the same difficulty level and the same set of tasks, a reader can assume those two scenarios are comparable. Similarly, lower difficulty and/or fewer tasks can be assumed to result in an easier scenario, higher difficulty and/or more tasks can be assumed to result in a harder scenario, etc.

<h3>Score Calculation</h3>

OpenMATBC comes with a score calculation script. This script can analyse OpenMATB logs from an experiment run and produce performance statistics for each task. This includes both standard statistics, such as the time the Tracking task cursor was in the target area, and an overall 'score' for each task. This score is a value between 0 and 1 defined so that '0' can be considered the worst possible performance and '1' considered the best possible performance.

This tool is particularly helpful for the use of MATB as a research tool as determining performance from the raw event logs can be difficult. In addition, different research tends to assess performance based on different metrics. This score calculation script provides an easy to use scoring system that can be used in a variety of research. This is particularly true when used in conjunction with the scenario generator, as the scores achieved in different research using similarly generated scenarios can be compared more easily.

<h3>Other Differences to OpenMATB</h3>

A range of smaller tweaks and bug fixes have been made to OpenMATBC when compared to the base OpenMATB version on which this project was built. In addition, OpenMATB itself has seen a number of updates since the version OpenMATBC was built on was pulled. The addition of the networking code makes reconciling the two versions difficult, so it can be assumed there are a significant number of other differences between OpenMATBC and the current version of OpenMATB.

<h2>Installation</h2>

The program requires Python 3.x (tested on version 3.9 and 3.10) and the following libraries, freely available online: PySide2, Pygame, rstr, numpy, psutil, toml, and Twisted. These can be installed via `pip install -r requirements.txt`. Make sure you install the matching (32- or 64-bit) version of Pygame as your Python installation, and the one compatible with your Python version number.

The program was tested under Windows only, though we have no reason to believe it would be difficult to get to work on Linux.

To run perfectly, the software requires only a personal computer and a joystick for the tracking and collaborative matching tasks. 

OpenMATBC inherits the GPL v3 license from the base version of OpenMATB it was built from. The original authors chose this licence to promote exchange between researchers, granting them the permission not only to run and to study the source code, but also to share their software modifications.


<h3>Documentation</h3>

For detailed documentation on running OpenMATBC, creating scenarios, configuring tasks, and using the scenario generator, please see the <a href="../../wiki">OpenMATBC Wiki</a>.

<h3>Notes</h3>

<ul>
<li>The <code>staticfeedback</code> plugin is inherited from the base OpenMATB project and is not fully supported in OpenMATBC.</li>
</ul>

<h3>Original OpenMATB Resources</h3>

The following resources from the original OpenMATB project may also be useful:

<ul>
<li><a href="https://github.com/juliencegarra/OpenMATB/wiki">Original OpenMATB Wiki</a></li>
</ul>





