def render_invitation_email(*, name: str, link: str, origin: str) -> str:
    return f"""<!DOCTYPE html>
<html>
<head><meta charset="utf-8"></head>
<body style="margin:0;padding:0;background:#f8fafc;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;">
  <table width="100%" cellpadding="0" cellspacing="0"><tr><td align="center" style="padding:40px 16px;">
    <table width="560" cellpadding="0" cellspacing="0" style="background:#ffffff;border-radius:12px;overflow:hidden;border:1px solid #e2e8f0;">
      <tr><td style="background:#1e293b;padding:20px 24px;">
        <table cellpadding="0" cellspacing="0"><tr>
          <td style="width:32px;height:32px;background:#2563eb;border-radius:6px;text-align:center;vertical-align:middle;color:#ffffff;font-weight:700;font-size:16px;">ST</td>
          <td style="padding-left:10px;color:#ffffff;font-weight:600;font-size:14px;">Sistema de Turnos Médicos</td>
        </tr></table>
      </td></tr>
      <tr><td style="padding:32px;">
        <p style="color:#475569;font-size:14px;margin:0 0 8px;">Hola <strong>{name}</strong>,</p>
        <p style="color:#475569;font-size:14px;margin:0 0 20px;">
          Se ha creado una cuenta para ti en el Sistema de Turnos Médicos. Haz clic en el siguiente enlace para establecer tu contraseña:
        </p>
        <table cellpadding="0" cellspacing="0" style="margin:24px auto;"><tr>
          <td style="background:#2563eb;border-radius:6px;padding:0;">
            <a href="{link}" style="display:inline-block;padding:12px 32px;color:#ffffff;text-decoration:none;font-weight:600;font-size:14px;">Establecer contraseña</a>
          </td>
        </tr></table>
        <p style="font-size:12px;color:#94a3b8;text-align:center;margin:0 0 20px;word-break:break-all;">
          O copia este enlace en tu navegador:<br>
          <span style="color:#2563eb;">{link}</span>
        </p>
        <hr style="border:none;border-top:1px solid #e2e8f0;margin:20px 0;">
        <p style="font-size:12px;color:#94a3b8;margin:0 0 4px;">⏰ Este enlace expira en <strong>48 horas</strong> y solo puede usarse una vez.</p>
        <p style="font-size:12px;color:#94a3b8;margin:0;">Si no solicitaste esta cuenta, ignora este mensaje.</p>
        <p style="font-size:12px;color:#cbd5e1;margin:8px 0 0;">Sistema de Turnos Médicos — Hospital Regional</p>
      </td></tr>
    </table>
  </td></tr></table>
</body>
</html>"""
