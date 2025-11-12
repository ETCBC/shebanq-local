let sortTable = (columnIndex, asc, asString) => {
  const table = document.getElementById("queries")
  const rows = Array.from(table.tBodies[0].rows)

  const sortedRows = rows.sort((a, b) => {
    const cellA = a.cells[columnIndex].getAttribute("key")
    const cellB = b.cells[columnIndex].getAttribute("key")
    return asString
      ? asc
        ? cellA.localeCompare(cellB)
        : cellB.localeCompare(cellA)
      : asc
      ? Number.parseInt(cellA) - Number.parseInt(cellB)
      : Number.parseInt(cellB) - Number.parseInt(cellA)
  })

  sortedRows.forEach(row => table.tBodies[0].appendChild(row))
}

let filterTable = () => {
  const table = document.getElementById("queries")
  const filterRow = table.tHead.rows.item(1)
  const filters = Array.from(filterRow.getElementsByTagName("input")).map(
    x => x.value.toLowerCase()
  )
  const hasFilter = filters.join("")
  const rows = table.tBodies[0].rows

  if (!hasFilter) {
    for (const row of rows) {
      row.style.display = ""
    }
    return
  }

  for (const row of rows) {
    const cells = row.getElementsByTagName("td")

    let match = true

    let c = 0
    for (const cell of cells) {
      const filter = filters[c]
      c += 1

      if (!filter) {
        continue
      }
      const cellText = cell.getAttribute("key")

      if (!cellText.includes(filter)) {
        match = false
        break
      }
    }
    row.style.display = match ? "" : "none"
  }
}

let navigate = () => {
  const urlParams = new URLSearchParams(window.location.search);
  const qId = urlParams.get('id');
  console.warn({ qId })

  const table = document.getElementById("queries")
  const rows = table.tBodies[0].rows

  for (const row of rows) {
    const cell = row.getElementsByTagName("td").item(0)
    const cellText = cell.getAttribute("key")

    if (cellText == qId) {
      row.scrollIntoView({ behavior: "smooth", block: "center" })
      row.classList.add("active")
    }
    else {
      row.classList.remove("active")
    }
  }
}

document.addEventListener("DOMContentLoaded", () => navigate())
