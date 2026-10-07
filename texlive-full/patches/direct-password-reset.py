#!/usr/bin/env python3
"""With TEXNEST_DIRECT_PASSWORD_RESET=true, "Forgot your password?" redirects straight to the set-password page.
Each edit must match Overleaf's current code exactly; otherwise the build stops here so the patch can be reviewed."""
WEB = "/overleaf/services/web"


def edit(path, old, new):
    s = open(path).read()
    if old not in s:
        raise SystemExit(f"patch no longer matches {path}; update texlive-full/patches/direct-password-reset.py")
    open(path, "w").write(s.replace(old, new, 1))


edit(f"{WEB}/app/src/Features/PasswordReset/PasswordResetHandler.mjs",
     """  const emailOptions = {
    to: email,
    setNewPasswordUrl: `${
      settings.siteUrl
    }/user/password/set?passwordResetToken=${token}&email=${encodeURIComponent(
      email
    )}`,
  }

  await EmailHandler.promises.sendEmail('passwordResetRequested', emailOptions)

  return 'primary'
""",
     """  const setNewPasswordUrl = `${settings.siteUrl}/user/password/set?passwordResetToken=${token}&email=${encodeURIComponent(email)}`

  // TeXnest: send the user to the page directly instead of e-mailing the link.
  if (process.env.TEXNEST_DIRECT_PASSWORD_RESET === 'true') {
    return { status: 'primary', setNewPasswordUrl }
  }

  await EmailHandler.promises.sendEmail('passwordResetRequested', { to: email, setNewPasswordUrl })

  return 'primary'
""")

edit(f"{WEB}/app/src/Features/PasswordReset/PasswordResetController.mjs",
     """  if (status === 'primary') {
    return res.status(200).json({
      message: req.i18n.translate('password_reset_email_sent'),
    })
  } else if (status === 'secondary') {""",
     """  if (status && status.setNewPasswordUrl) {
    // TeXnest: direct password reset, no e-mail involved
    return res.status(200).json({ redir: status.setNewPasswordUrl })
  }
  if (status === 'primary') {
    return res.status(200).json({
      message: req.i18n.translate('password_reset_email_sent'),
    })
  } else if (status === 'secondary') {""")

edit(f"{WEB}/locales/en.json",
     '"enter_your_email_address_below_and_we_will_send_you_a_link_to_reset_your_password": "Enter your email address below, and we will send you a link to reset your password",',
     '"enter_your_email_address_below_and_we_will_send_you_a_link_to_reset_your_password": "Enter the email address of your account to reset its password",')
print("direct password reset patch applied")
