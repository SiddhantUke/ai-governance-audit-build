function ensureSidebar() {
  var sidebar = document.getElementById("authSidebar");
  if (!sidebar) {
    sidebar = document.createElement("aside");
    sidebar.id = "authSidebar";
    var brand = document.createElement("div");
    brand.textContent = "AI Governance Audit Platform";
    brand.style.fontSize = "17px";
    brand.style.fontWeight = "700";
    brand.style.color = "#0b2a4a";
    brand.style.marginBottom = "12px";
    brand.style.lineHeight = "1.3";
    sidebar.appendChild(brand);
    var navLinks = [
      ["Library", "#frameworks"],
      ["Inventory", "#inventory"],
      ["Upload", "#uploadFile"],
      ["Audit", "#runBtn"],
      ["Review", "#review"],
      ["Report", "#report"]
    ];
    var nav = document.createElement("nav");
    navLinks.forEach(function(item) {
      var link = document.createElement("a");
      link.textContent = item[0];
      link.href = item[1];
      link.style.display = "block";
      link.style.color = "#0b2a4a";
      link.style.textDecoration = "none";
      link.style.padding = "8px 10px";
      link.style.borderRadius = "8px";
      link.style.margin = "3px 0";
      link.style.fontSize = "14px";
      link.style.fontWeight = "600";
      nav.appendChild(link);
    });
    sidebar.appendChild(nav);
    var heading = document.createElement("h3");
    heading.textContent = "Account";
    heading.style.marginTop = "20px";
    sidebar.appendChild(heading);
    var note = document.createElement("p");
    note.className = "muted";
    note.textContent = "Sign in to connect to the live backend.";
    sidebar.appendChild(note);
    document.body.insertBefore(sidebar, document.body.firstChild);
  }
  return sidebar;
}
