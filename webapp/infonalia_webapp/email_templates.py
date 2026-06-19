from __future__ import annotations

import html


LOGO_CID = "cid:llangon-logo"


def build_llangon_email_shell(
    *,
    eyebrow: str,
    title: str,
    body_html: str,
    subtitle: str = "",
    footer_left_html: str = "",
    footer_right_html: str = "",
    closing_html: str = "",
    logo_alt: str = "Asesores Llangón",
) -> str:
    safe_eyebrow = html.escape(eyebrow)
    safe_title = html.escape(title)
    safe_subtitle = html.escape(subtitle)
    safe_logo_alt = html.escape(logo_alt)
    subtitle_html = (
        f'<p style="margin:6px 0 0 0; color:#667085; font-size:14px; line-height:1.35;">{safe_subtitle}</p>'
        if safe_subtitle
        else ""
    )
    footer_html = ""
    if footer_left_html or footer_right_html:
        footer_html = f"""
            <tr>
              <td style="padding:18px 28px; background:#eaf7ea; border-top:1px solid #d9e2ec;">
                <table width="100%" cellpadding="0" cellspacing="0" style="border-collapse:collapse;">
                  <tr>
                    <td style="color:#1f7a4d; font-size:13px; font-weight:700;">{footer_left_html}</td>
                    <td align="right" style="color:#667085; font-size:13px;">{footer_right_html}</td>
                  </tr>
                </table>
              </td>
            </tr>"""
    closing_block = ""
    if closing_html:
        closing_block = f"""
            <tr>
              <td style="padding:16px 28px; color:#667085; font-size:12px; line-height:1.4;">
                {closing_html}
              </td>
            </tr>"""

    return f"""<!doctype html>
<html lang="es">
  <body style="margin:0; padding:0; background:#f5f7fb; font-family:Calibri, Segoe UI, Arial, sans-serif; color:#1f2937;">
    <table width="100%" cellpadding="0" cellspacing="0" style="background:#f5f7fb; padding:22px 12px; border-collapse:collapse;">
      <tr>
        <td align="center">
          <table width="100%" cellpadding="0" cellspacing="0" style="max-width:680px; background:#ffffff; border:1px solid #d9e2ec; border-radius:10px; overflow:hidden; border-collapse:collapse;">
            <tr>
              <td style="padding:18px 24px; border-bottom:1px solid #d9e2ec;">
                <table width="100%" cellpadding="0" cellspacing="0" style="border-collapse:collapse;">
                  <tr>
                    <td style="vertical-align:middle;">
                      <p style="margin:0 0 4px 0; color:#667085; font-size:12px; font-weight:800; text-transform:uppercase;">{safe_eyebrow}</p>
                      <h1 style="margin:0; color:#1f2937; font-size:20px; line-height:1.2;">{safe_title}</h1>
                      {subtitle_html}
                    </td>
                    <td align="right" style="vertical-align:middle;">
                      <img src="{LOGO_CID}" alt="{safe_logo_alt}" style="display:block; max-width:128px; height:auto;">
                    </td>
                  </tr>
                </table>
              </td>
            </tr>
            <tr>
              <td style="padding:22px 24px;">
                {body_html}
              </td>
            </tr>
            {footer_html}
            {closing_block}
          </table>
        </td>
      </tr>
    </table>
  </body>
</html>"""
