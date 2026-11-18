# Starship prompt for FreeBSD sh. 13.2's sh can't run commands inside PS1, so
# the prompt is recomputed at login and after every cd (no git/duration
# refresh between commands). Its line editor (libedit) also strips ESC bytes
# from prompts, so colours come out as garbage ("[1;48;2;...m"): ANSI is
# removed and the prompt is plain text. Install bash for the full coloured
# prompt (starship init bash).
case $- in *i*)
  if [ -x "$HOME/.local/bin/starship" ]; then
    PATH="$HOME/.local/bin:$PATH"; export PATH
    __sp_set() {
      _e=$(printf '\033')
      PS1="$(STARSHIP_SHELL=sh starship prompt 2>/dev/null | sed -e "s/${_e}\\[[0-9;]*m//g") "
    }
    cd() { command cd "$@" && __sp_set; }
    __sp_set
  fi ;;
esac
