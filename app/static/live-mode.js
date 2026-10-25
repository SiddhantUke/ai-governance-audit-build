(function () {
  var companyHtml = '<p><strong>NovaFin Technologies (fictional demo company)</strong> — Fintech. Digital lending and payments company using AI across hiring, support, credit, marketing and fraud.</p>';

  function removeOfflineButton() {
    var buttons = document.querySelectorAll("button");
    for (var i = 0; i < buttons.length; i++) {
      if (buttons[i].textContent.trim().toLowerCase().indexOf("back to offline") !== -1) {
        buttons[i].remove();
      }
    }
  }
  removeOfflineButton();
  window.addEventListener("load", removeOfflineButton);
  setTimeout(removeOfflineButton, 1000);

  try {
    var savedRender = (typeof renderConnectedLibrary === "function") ? renderConnectedLibrary : null;
    if (savedRender) {
      renderConnectedLibrary = function () {
        var result = savedRender.apply(null, arguments);
        function prependHeader() {
          var invEl = document.getElementById("inventory");
          if (invEl && invEl.innerHTML.indexOf("NovaFin Technologies") === -1) {
            invEl.innerHTML = companyHtml + invEl.innerHTML;
          }
        }
        if (result && typeof result.then === "function") {
          result.then(prependHeader);
        } else {
          prependHeader();
        }
        return result;
      };
    }
  } catch (e) {}

  var triedToken = null;
  function tryAutoConnect() {
    var token = localStorage.getItem("gov_audit_token");
    if (!token) {
      return;
    }
    if (typeof CONNECTED !== "undefined" && CONNECTED) {
      return;
    }
    if (typeof connectBackend !== "function") {
      return;
    }
    if (triedToken === token) {
      return;
    }
    triedToken = token;
    try {
      var p = connectBackend();
      if (p && typeof p.catch === "function") {
        p.catch(function () {});
      }
    } catch (e) {}
  }
  tryAutoConnect();
  setInterval(tryAutoConnect, 1000);
})();
