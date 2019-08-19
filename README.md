
# project : Item Catalog

# step to run this project on virtual machine

=> Download [virtual box](https://www.virtualbox.org/wiki/Download_Old_Builds_5_1) and install it.

=> Download [vagrant](https://www.vagrantup.com/downloads.html) and install it.

=> If you are using windows you can download [git bash](https://git-scm.com/downloads) to run commands.For Linux or Mac regular terminal program will run fine.

=> Clone the [repository](https://github.com/udacity/fullstack-nanodegree-vm) and go to this downloaded directory , you will find another directory called vagrant. Change directory to the vagrant directory.

=> From your terminal, inside the vagrant subdirectory, run the command "vagrant up".When "vagrant up" is finished running, you will get your shell prompt back. At this point, you can run "vagrant ssh" to log in to your newly installed Linux VM.

=> After log in, go to catalog folder, and run 'python database_setup.py'.

=> Then run command 'python categories.py' to add default categories in catalog.

=> At the end you can just run 'python application.py' and can enjoy item catalog project.