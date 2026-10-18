AutoForm favicon pack

Copy the files to your frontend site root (often frontend/). Add inside <head> on each HTML page:

<link rel="icon" type="image/svg+xml" href="/favicon.svg">
<link rel="icon" type="image/png" sizes="32x32" href="/favicon-32.png">
<link rel="icon" type="image/png" sizes="16x16" href="/favicon-16.png">
<link rel="shortcut icon" href="/favicon.ico">
<link rel="apple-touch-icon" sizes="180x180" href="/apple-touch-icon.png">

If hosted under a subpath, adjust href paths. Hard-refresh after adding.
