# Shell Completion configuration

It is possible to configure shell command completion for systems that use the bash, zsh or fish shells (Linux and Mac basically). To set it up run the following command:

```text
    _OIC_COMPLETE=bash_source oic > ~/.oic-complete.bash
```

Then add the following line to your ~/.bashrc file (the leading period and space are important):

```text
    . ~/.oic-complete.bash
```

Once you login again you should then be able to press Tab to complete command and option names. Pressing Tab twice will display the list of possible options. For example:

```text
    $ oic <tab><tab>
    cache       cmd         listparams  log         save        serialno
    can         dumpall     load        read        scan        write
    $ oic log -<tab><tab>
    -s              --timestamp     --help
    --step          --no-timestamp
```
