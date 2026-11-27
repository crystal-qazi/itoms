/* Filter report field choices to the selected allowlisted dataset. */
document.addEventListener("DOMContentLoaded", function () {
  const dataset = document.getElementById("report-dataset");
  const columns = document.getElementById("report-columns");
  if (!dataset || !columns) return;

  function filterFields() {
    const selected = dataset.value;
    Array.from(columns.options).forEach(function (option) {
      const visible = option.dataset.dataset === selected;
      option.hidden = !visible;
      option.disabled = !visible;
      if (!visible) option.selected = false;
    });
    const first = Array.from(columns.options).find(function (option) {
      return !option.disabled;
    });
    if (first && !Array.from(columns.options).some(function (option) {
      return option.selected;
    })) first.selected = true;
  }

  dataset.addEventListener("change", filterFields);
  filterFields();
});
