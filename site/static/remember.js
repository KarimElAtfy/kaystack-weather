// The town chosen last time, kept in this browser only (no cookie).
// On the selector it opens that town before the page paints, with replace() so
// Back does not return here; on the text pages it fills in the link back to it.
(function () {
  var towns = document.querySelector('meta[name="towns"]');
  var known = towns ? towns.content.split(' ') : [];
  var town = null;
  try {
    town = localStorage.getItem('meteo.town');
  } catch (e) {
    return;
  }
  if (known.indexOf(town) < 0) return;
  if (location.pathname === '/') {
    location.replace('/' + town);
    return;
  }
  var back = document.querySelector('a[data-back]');
  if (!back) return;
  var labels = JSON.parse(back.getAttribute('data-back'));
  back.href = '/' + town;
  back.textContent = labels[town];
  back.hidden = false;
})();
