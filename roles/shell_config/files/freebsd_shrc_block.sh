# Starship prompt for FreeBSD sh (13.2 can't run commands inside PS1, so the
# prompt is recomputed at login and after every cd; no git/duration segments
# until it's refreshed). Starship's bash mode wraps escapes in \[ \]; libedit
# wants \001 instead.
case $- in *i*)
  if [ -x "$HOME/.local/bin/starship" ]; then
    PATH="$HOME/.local/bin:$PATH"; export PATH
    __sp_set() {
      _c=$(printf '\001')
      PS1="$(STARSHIP_SHELL=bash starship prompt 2>/dev/null | sed -e 's/\\\[/'"$_c"'/g' -e 's/\\\]/'"$_c"'/g') "
    }
    cd() { command cd "$@" && __sp_set; }
    __sp_set
  fi ;;
esac
