
function setup_showhide(show_button, hide_button, content)
{
    $(content).hide();

    $(show_button).click(function(){
        $(show_button).fadeOut("fast");
        $(content).slideDown("slow");
        return false;
    });
    $(hide_button).click(function(){
        $(show_button).fadeIn("slow");
        $(content).slideUp("fast");
        return false;
    });
}

function init_default_text()
{
    $(".default_text").focus(function(srcc)
    {
        if ($(this).val() == $(this)[0].title)
        {
            $(this).removeClass("default_text_active");
            $(this).val("");
        }
    });
    
    $(".default_text").blur(function()
    {
        if ($(this).val() == "")
        {
            $(this).addClass("default_text_active");
            $(this).val($(this)[0].title);
        }
    });
    
    $(".default_text").blur();
}

function initialize()
{
    init_default_text();

    $('img.captify').captify({
        // all of these options are... optional
        // ---
        // speed of the mouseover effect
        speedOver: 'fast',
        // speed of the mouseout effect
        speedOut: 'normal',
        // how long to delay the hiding of the caption after mouseout (ms)
        hideDelay: 500, 
        // 'fade', 'slide', 'always-on'
        animation: 'slide',     
        // text/html to be placed at the beginning of every caption
        prefix: '',     
        // opacity of the caption on mouse over
        opacity: '0.7',                 
        // the name of the CSS class to apply to the caption box
        className: 'caption-bottom',    
        // position of the caption (top or bottom)
        position: 'bottom',
        // caption span % of the image
        spanWidth: '100%'
    });

    setup_showhide('#add_image', '#hide_images_add', '#images_add_form')
    setup_showhide('#add_video', '#hide_videos_add', '#videos_add_form')
    
    $('.elastic').elastic();
}

function expandtextarea(button, post_form, textbox, user_anonymous,
                    ref_path)
{
    if ('True' == user_anonymous)
    {
        window.location="/login/?next="+ref_path
    }
    else
    {
        window.setTimeout(function(){
            $(button).hide();
            $(post_form).show();
            $(textbox).focus();}, 100);
    }
}
