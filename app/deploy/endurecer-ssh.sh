#!/usr/bin/env bash
# Endurece o SSH da VM depois das tentativas de senha de 30/10 a 09/11/2026.
#  1. Firewall: a porta 22 só aceita conexão vinda da rede interna do LARCC (onde fica o salto).
#  2. sshd: de fora dessa rede, ninguém entra por senha nem como root; 3 tentativas por conexão.
#  3. fail2ban: 5 senhas erradas em 10 min bloqueiam o IP (1 h, dobrando se repetir).
# Roda como root na VM (pode rodar de novo, não duplica nada):
#   Get-Content app/deploy/endurecer-ssh.sh -Raw | ssh -J "$SALTO_SSH" "root@$VM" 'SALTO=... REDE_LARCC=... bash -s'
# (SALTO_SSH = usuario@host:porta do salto do LARCC; VM = IP interno da VM. Não ficam no repositório.)
# Segurança contra ficar trancado do lado de fora: tudo se desfaz sozinho em 10 min.
# Depois de testar que uma conexão NOVA entra, confirme com:  systemctl stop desfazer-ssh.timer
set -euo pipefail
SALTO=${SALTO:?defina SALTO=<IP interno do salto do LARCC>}   # de onde vêm os nossos acessos
REDE_LARCC=${REDE_LARCC:?defina REDE_LARCC=<rede interna do LARCC, ex. 10.0.0.0/24>}
VM_IP=$(hostname -I | awk '{print $1}')

BK=/root/ssh-antes-$(date +%Y%m%d-%H%M%S)
mkdir -p "$BK"
cp -a /etc/ssh "$BK/"
ufw status numbered > "$BK/ufw.txt"

# --- 0. desfazer automático em 10 min ---
cat > /root/desfazer-ssh.sh <<EOF
#!/bin/bash
# Volta o SSH e o firewall como estavam antes de $(date +%F)
rm -f /etc/ssh/sshd_config.d/01-acervo.conf
cp -a $BK/ssh/sshd_config /etc/ssh/sshd_config
ufw allow 22/tcp
systemctl reload ssh
echo "desfeito em \$(date)" >> /root/desfazer-ssh.log
EOF
chmod 700 /root/desfazer-ssh.sh
systemctl stop desfazer-ssh.timer 2>/dev/null || true
systemd-run --quiet --unit=desfazer-ssh --on-active=600 /bin/bash /root/desfazer-ssh.sh
echo "desfazer automático marcado para daqui a 10 min (backup em $BK)"

# --- 1. sshd ---
# Arquivo 01-: o primeiro valor lido vale, então isto ganha dos outros arquivos.
cat > /etc/ssh/sshd_config.d/01-acervo.conf <<'EOF'
# Acervo Psico: de fora da rede do LARCC ninguém entra por senha nem como root.
PermitRootLogin no
PasswordAuthentication no
KbdInteractiveAuthentication no
MaxAuthTries 3
LoginGraceTime 30
EOF
# O bloco Match vale até o fim do arquivo, por isso fica no fim do arquivo principal.
if ! grep -q 'acervo-psico: rede do LARCC' /etc/ssh/sshd_config; then
  cat >> /etc/ssh/sshd_config <<EOF

# acervo-psico: rede do LARCC (salto) continua entrando como root com senha
Match Address $REDE_LARCC
    PermitRootLogin yes
    PasswordAuthentication yes
EOF
fi
sshd -t
systemctl reload ssh

# --- 2. firewall ---
ufw allow from "$REDE_LARCC" to any port 22 proto tcp comment 'SSH so pela rede do LARCC' >/dev/null
ufw --force delete allow 22/tcp >/dev/null 2>&1 || true

# --- 3. fail2ban ---
if ! command -v fail2ban-client >/dev/null; then
  DEBIAN_FRONTEND=noninteractive apt-get install -y -q fail2ban >/dev/null
fi
cat > /etc/fail2ban/jail.d/acervo.local <<EOF
[DEFAULT]
# nunca bloquear o salto: todos os nossos acessos vêm dele
ignoreip = 127.0.0.1/8 ::1 $SALTO
bantime = 1h
bantime.increment = true
findtime = 10m
maxretry = 5

[sshd]
enabled = true
backend = systemd
EOF
fail2ban-client -t >/dev/null
systemctl enable -q fail2ban
systemctl restart fail2ban
sleep 2

# --- conferência ---
echo; echo "== sshd para alguém de fora (ex.: o atacante 209.99.188.168) =="
sshd -T -C user=root,host=x,addr=209.99.188.168,laddr=$VM_IP,lport=22 | grep -E '^(permitrootlogin|passwordauthentication|maxauthtries)'
echo "== sshd para o salto ($SALTO) =="
sshd -T -C user=root,host=x,addr=$SALTO,laddr=$VM_IP,lport=22 | grep -E '^(permitrootlogin|passwordauthentication|maxauthtries)'
echo "== firewall =="; ufw status | sed -n '4,20p'
echo "== fail2ban =="; fail2ban-client status sshd
