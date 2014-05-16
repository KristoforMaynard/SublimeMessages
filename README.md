SublimeMessages
===============

A manager for messages that belong to a line of code in Sublime Text. This plugin handles creating gutter marks for lines with messages and changing the status bar to relay the message when the cursor changes lines. Unlike similar plugins, this one keeps track of gutters when the file changes. This plugin depends on other Message\* plugins to work. The idea being plugins like MessagesPylint will generate python lint messages, and tell this plugin about them.

Gutter mark colors are determined by the following scopes in your color scheme:
 - SublimeMessages.error
 - SublimeMessages.warning
 - SublimeMessages.info
