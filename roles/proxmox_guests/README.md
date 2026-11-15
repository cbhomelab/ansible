
## Restore-test pitfall (vzdump)
A restored guest keeps the original MAC, onboot=1 and protection=1. Before booting a scratch restore: delete net0, set onboot=0 and protection=0, or it collides on the bridge and cannot be destroyed.
