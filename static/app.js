// Attach submit handler to the form
$("#searchForm").submit(function(event) {

  // Stop form from submitting normally
  event.preventDefault();

  // Get some values from elements on the page:
  const $form = $(this);
  const device = $form.find("input[name='device']").val();
  const product_code = $form.find("input[name='product_code']").val();
  const url = $form.attr("action");

  // Send the data using post
  const posting = $.post(url, {device,product_code});

  // Put the results in a div
  posting.done(function(data) {
    // const content = $(data).find("#content");
    console.log(data)
    $("#result").empty().append(data);
    // $("#result").append(content);
    // $("#result").html(content)
  });
});