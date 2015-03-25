SublimeMessages
===============

A manager for messages that belong to a line of code in Sublime Text. This plugin handles creating gutter marks for lines with messages and changing the status bar to relay the message when the cursor changes lines. Unlike similar plugins, this one keeps track of gutters when the file changes. This plugin depends on other Message\* plugins to work. The idea being plugins like [SublimeMessagesPylint] will generate python lint messages, and tell this plugin about them.

Plugins
-------

  - [SublimeMessagesPylint]
  - [SublimeMessagesSublemake]

Gutter Icon Options
-------------------

In your Messages.sublime-settings file, you can set `icon_style` to one of ["default16" (default), "default32", "blank16", "blank32", "dots"]. The number is the size of the icon in pixels (32 is for high dpi machines). The default icons have their own color and the the blank icons can be colorized by your color scheme. The keys in the color scheme are:

 - `SublimeMessages.error`
 - `SublimeMessages.warning`
 - `SublimeMessages.info`
 - `SublimeMessages.unknown`

Note
----

The settings for this and all associated plugins are automatically read using [multiconf.py](https://gist.github.com/facelessuser/3625497). Settings filenames are `Messages<PluginName>.sublime-settings`.

[SublimeMessagesPylint]: https://github.com/KristoforMaynard/SublimeMessagesPylint
[SublimeMessagesSublemake]: https://github.com/KristoforMaynard/SublimeMessagesSublemake
