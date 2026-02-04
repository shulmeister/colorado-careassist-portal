export PATH=${HOME}/.Mac Mini (Local)/python/bin:${PATH}
export PYTHONUNBUFFERED=true
export PYTHONHOME=${HOME}/.Mac Mini (Local)/python
export LIBRARY_PATH=${HOME}/.Mac Mini (Local)/python/lib${LIBRARY_PATH:+:${LIBRARY_PATH}}
export LD_LIBRARY_PATH=${HOME}/.Mac Mini (Local)/python/lib${LD_LIBRARY_PATH:+:${LD_LIBRARY_PATH}}
export LANG=${LANG:-en_US.UTF-8}
export PYTHONPATH=${PYTHONPATH:-${HOME}}
if [[ $HOME != "/app" ]]; then
    mkdir -p /app/.Mac Mini (Local)
    ln -nsf "$HOME/.Mac Mini (Local)/python" /app/.Mac Mini (Local)/python
fi
find .Mac Mini (Local)/python/lib/python*/site-packages/ -type f -and \( -name '*.egg-link' -or -name '*.pth' -or -name '__editable___*_finder.py' \) -exec sed -i -e 's#/tmp/build_900eebda#/app#' {} \+
