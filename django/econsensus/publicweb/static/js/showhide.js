/*
Show/hide the feedback_comment class amongst multiple,
with activation via a show button
Objects are automatically hidden if the 
user clicks outside the area
*/
  $(document).ready(function() {
    $("body").live("click", function() {
      $(".form_comment").hide();
    });
    
    $(".show").live("click", function(e) {
      var this_comment_form  = $(this).parent().siblings().find(".form_comment");
      $(".form_comment").hide();
      this_comment_form.show();
      // Ensure "Post" button is on screen
      this_comment_form.find(".button").focus();
      // Move focus to where user will type
      this_comment_form.find("textarea").focus();
      e.stopPropagation();
      e.preventDefault();
    });
    
    $(".form_comment").live("click", function(e) {
      e.stopPropagation();
    });
  });
