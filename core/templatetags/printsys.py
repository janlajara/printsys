from django import template
from django.urls import reverse_lazy
from django.template.loader import render_to_string
register = template.Library()


@register.simple_tag(takes_context=True)
def custom_header_title(context):
    parts = []
    opts = context.get("opts")
    current_app = (
        context.request.current_app
        if hasattr(context.request, "current_app")
        else "admin"
    )

    if opts:
        # We override the root breadcrumb item to always point to the home page
        parts.append(
            {
                "link": '/admin', 
                "title": "Home",
            }
        )

        if (original := context.get("original")) and not isinstance(original, str):
            parts.append(
                {
                    "link": reverse_lazy(
                        f"{current_app}:{original._meta.app_label}_{original._meta.model_name}_changelist"
                    ),
                    "title": original._meta.verbose_name_plural,
                }
            )

            parts.append(
                {
                    "link": reverse_lazy(
                        f"{current_app}:{original._meta.app_label}_{original._meta.model_name}_change",
                        args=[original.pk],
                    ),
                    "title": original,
                }
            )
        elif object := context.get("object"):
            parts.append(
                {
                    "link": reverse_lazy(
                        f"{current_app}:{object._meta.app_label}_{object._meta.model_name}_changelist"
                    ),
                    "title": object._meta.verbose_name_plural,
                }
            )

            parts.append(
                {
                    "link": reverse_lazy(
                        f"{current_app}:{object._meta.app_label}_{object._meta.model_name}_change",
                        args=[object.pk],
                    ),
                    "title": object,
                }
            )
        else:
            parts.append(
                {
                    "link": reverse_lazy(
                        f"{current_app}:{opts.app_label}_{opts.model_name}_changelist"
                    ),
                    "title": opts.verbose_name_plural,
                }
            )
    elif object := context.get("object"):
        parts.append(
            {
                "link": reverse_lazy(
                    f"{current_app}:app_list", args=[object._meta.app_label]
                ),
                "title": object._meta.app_label,
            }
        )

        parts.append(
            {
                "link": reverse_lazy(
                    f"{current_app}:{object._meta.app_label}_{object._meta.model_name}_changelist",
                ),
                "title": object._meta.verbose_name_plural,
            }
        )

        parts.append(
            {
                "link": reverse_lazy(
                    f"{current_app}:{object._meta.app_label}_{object._meta.model_name}_change",
                    args=[object.pk],
                ),
                "title": object,
            }
        )
    elif (model_admin := context.get("model_admin")) and hasattr(model_admin, "model"):
        parts.append(
            {
                "link": reverse_lazy(
                    f"{current_app}:app_list", args=[model_admin.model._meta.app_label]
                ),
                "title": model_admin.model._meta.app_label,
            }
        )

        parts.append(
            {
                "link": reverse_lazy(
                    f"{current_app}:{model_admin.model._meta.app_label}_{model_admin.model._meta.model_name}_changelist",
                ),
                "title": model_admin.model._meta.verbose_name_plural,
            }
        )

    if not opts and (content_title := context.get("content_title")):
        parts.append(
            {
                "title": content_title,
            }
        )

    if len(parts) == 0:
        username = (
            context.request.user.get_short_name() or context.request.user.get_username()
        )
        parts.append({"title": f"{_('Welcome')} {username}"})

    return render_to_string(
        "unfold/helpers/header_title.html",
        request=context.request,
        context={
            "parts": parts,
        },
    )