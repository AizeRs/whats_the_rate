// Runs in <head> before the page is drawn: things that must be in place before the body loads.

// Remember the visitor's timezone so the server can show update times in it
(function () {
    try {
        var tz = Intl.DateTimeFormat().resolvedOptions().timeZone;
        var had = document.cookie.indexOf('tz=' + encodeURIComponent(tz)) !== -1;
        if (tz && !had) {
            document.cookie = 'tz=' + encodeURIComponent(tz) + ';path=/;max-age=31536000;SameSite=Lax';
            // First visit (or timezone changed): reload once so the page is rendered with the right time
            if (document.cookie.indexOf('tz=' + encodeURIComponent(tz)) !== -1 && !sessionStorage.getItem('tzReloaded')) {
                sessionStorage.setItem('tzReloaded', '1');
                location.reload();
            }
        }
    } catch (e) {}
})();

// Asset logos (templates/_logo.html) are shown over the monogram once loaded and dropped if they fail.
// load/error don't bubble, so the listeners catch them on the way down; set up here, before any <img> exists.
document.addEventListener('load', function (e) {
    var img = e.target;
    if (img.classList && img.classList.contains('asset-logo')) {
        img.parentNode.classList.add(img.dataset.tile ? 'has-logo-tile' : 'has-logo');
    }
}, true);
document.addEventListener('error', function (e) {
    var img = e.target;
    if (img.classList && img.classList.contains('asset-logo')) img.remove();
}, true);
