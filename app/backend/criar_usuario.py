"""Cria (ou troca a senha de) um usuário do portal. Rodar DENTRO da VM:

    python criar_usuario.py <login> ["Nome para exibição"] [--admin]

A senha é pedida no terminal (ou lida de NOVA_SENHA) e gravada só como hash scrypt.
--admin: a conta vê o medidor de uso (/uso) e o uso dela não entra na contagem.
"""
import getpass
import os
import sys

import db
from seguranca import gerar_hash

args = [a for a in sys.argv[1:] if a != "--admin"]
admin = "--admin" in sys.argv[1:]
if not args:
    sys.exit(__doc__)
login = args[0].strip().lower()
nome = args[1] if len(args) > 1 else None
senha = os.environ.get("NOVA_SENHA") or getpass.getpass(f"Senha para '{login}': ")
if len(senha) < 8:
    sys.exit("A senha precisa ter pelo menos 8 caracteres.")

with db.conectar_admin() as conn:
    conn.execute(
        """INSERT INTO usuario (login, nome, hash_senha, admin) VALUES (%s, %s, %s, %s)
           ON CONFLICT (login) DO UPDATE
           SET hash_senha = EXCLUDED.hash_senha, nome = COALESCE(EXCLUDED.nome, usuario.nome),
               admin = EXCLUDED.admin, ativo = TRUE""",
        (login, nome, gerar_hash(senha), admin),
    )
    conn.commit()
print(f"usuário '{login}' pronto" + (" (administrador)" if admin else ""))
