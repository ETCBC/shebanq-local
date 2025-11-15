## `mounts denied` error

Docker allows your containers to mount directories on your file system.
But not all directories, only those are inside a specific list.
In the docker app you can see that list if you open the settings, navigate to
the Resources section, and click the File sharing tab. 
If you scroll down to Virtual file shares you see the list of places from which
you can share directories, and you can add a directory there as well.

So, either add a directory here, or move your shebanq-local under one of the
existing places.
