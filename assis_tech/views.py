from django.contrib.auth.models import User
from django.shortcuts import render, redirect
from django.http import HttpResponse
from django.forms import inlineformset_factory
from django.contrib.auth.forms import UserCreationForm
from assis_tech.form import CreateUserForm, AccountAuthenticationForm, AccountUpdateForm
from django.contrib.auth import authenticate, login, logout
import folium
import cv2
import json
import base64
import requests
import os
from django.core.files.storage import FileSystemStorage
from django.core.files.storage import default_storage
from django.core import files

from .form import RelatoForm
from .models import Relato
from django.core.paginator import Paginator
from .filters import RelatoFilter
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import render
from django.conf import settings
from .models import Account


# Create your views here.
TEMP_PROFILE_IMAGE_NAME = "temp_profile_image.png"


def index(request):
    # Create MAp
    m = folium.Map(location=[-26.900420999510086, -
                   49.08161133527756], zoom_start=15)
    folium.Marker(location=[-26.900420999510086, -49.08161133527756],
                  tooltop='clique para mais', popup='Centro POP').add_to(m)
    # Get html representation of map
    m = m._repr_html_()
    context = {
        'm': m,
    }
    return render(request, 'pages/index.html', context)


def registerPage(request):
    context = {}
    if request.method == "POST":
        form = CreateUserForm(request.POST)
        if form.is_valid():
            messages.add_message(request, messages.SUCCESS,
                                 'Usuário cadastrado com sucesso.')
            form.save()
        else:
            messages.add_message(request, messages.ERROR,
                                 'Falha ao Registrar Usuário.')
    return render(request, 'pages/register.html', context)


def loginPage(request):
    context = {}
    user = request.user
    if user.is_authenticated:
        return redirect('dashboard')
    if request.POST:
        form = AccountAuthenticationForm(request.POST)
        if form.is_valid():
            email = request.POST['email']
            password = request.POST['password']
            user = authenticate(email=email, password=password)
            if user:
                login(request, user)
                return redirect('dashboard')
        messages.add_message(request, messages.ERROR,
                             'Email ou Senha Inválido.')

        return redirect('login')

    else:
        form = AccountAuthenticationForm()

    context['login_form'] = form
    return render(request, 'pages/login.html', context)


def logoutUser(request):
    logout(request)
    return redirect('login')


def account_view(request, *args, **kwargs):
    """
    - Logic here is kind of tricky
            is_self (boolean)
                    is_friend (boolean)
                            -1: NO_REQUEST_SENT
                            0: THEM_SENT_TO_YOU
                            1: YOU_SENT_TO_THEM
    """
    context = {}
    user_id = kwargs.get("user_id")
    try:
        account = Account.objects.get(pk=user_id)
    except:
        return HttpResponse("Something went wrong.")
    if account:
        context['id'] = account.id
        context['username'] = account.username
        context['email'] = account.email
        context['profile_image'] = account.profile_image.url
        context['hide_email'] = account.hide_email
        # Define template variables
        is_self = True
        user = request.user
        if user.is_authenticated and user != account:
            is_self = False
        elif not user.is_authenticated:
            is_self = False
        # Set the template variables to the values
        context['is_self'] = is_self
        return render(request, "pages/account.html", context)


def edit_account_view(request, *args, **kwargs):
    if not request.user.is_authenticated:
        return redirect("login")
    user_id = kwargs.get("user_id")
    account = Account.objects.get(pk=user_id)
    if account.pk != request.user.pk:
        return HttpResponse("You cannot edit someone elses profile.")
    context = {}
    if request.POST:
        form = AccountUpdateForm(
            request.POST, request.FILES, instance=request.user)
        if form.is_valid():
            form.save()
            new_username = form.cleaned_data['username']
            return redirect("account:view", user_id=account.pk)
        else:
            form = AccountUpdateForm(request.POST, instance=request.user,
                                     initial={
                                         "id": account.pk,
                                         "email": account.email,
                                         "username": account.username,
                                         "profile_image": account.profile_image,
                                         "hide_email": account.hide_email,
                                     }
                                     )
            context['form'] = form
    else:
        form = AccountUpdateForm(
            initial={
                "id": account.pk,
                "email": account.email,
                "username": account.username,
                "profile_image": account.profile_image,
                "hide_email": account.hide_email,
            }
        )
        context['form'] = form
    context['DATA_UPLOAD_MAX_MEMORY_SIZE'] = settings.DATA_UPLOAD_MAX_MEMORY_SIZE
    return render(request, "pages/edit_account.html", context)


def save_temp_profile_image_from_base64String(imageString, user):
    INCORRECT_PADDING_EXCEPTION = "Incorrect padding"
    try:
        if not os.path.exists(settings.TEMP):
            os.mkdir(settings.TEMP)
        if not os.path.exists(settings.TEMP + "/" + str(user.pk)):
            os.mkdir(settings.TEMP + "/" + str(user.pk))
        url = os.path.join(settings.TEMP + "/" +
                           str(user.pk), TEMP_PROFILE_IMAGE_NAME)
        storage = FileSystemStorage(location=url)
        image = base64.b64decode(imageString)
        with storage.open('', 'wb+') as destination:
            destination.write(image)
            destination.close()
        return url
    except Exception as e:
        print("exception: " + str(e))
        # workaround for an issue I found
        if str(e) == INCORRECT_PADDING_EXCEPTION:
            imageString += "=" * ((4 - len(imageString) % 4) % 4)
            return save_temp_profile_image_from_base64String(imageString, user)
    return None


def crop_image(request, *args, **kwargs):
    payload = {}
    user = request.user
    print('-----ÓÓ----')
    if request.POST and user.is_authenticated:
        try:
            imageString = request.POST.get("image")
            url = save_temp_profile_image_from_base64String(imageString, user)
            img = cv2.imread(url)

            cropX = int(float(str(request.POST.get("cropX"))))
            cropY = int(float(str(request.POST.get("cropY"))))
            cropWidth = int(float(str(request.POST.get("cropWidth"))))
            cropHeight = int(float(str(request.POST.get("cropHeight"))))
            if cropX < 0:
                cropX = 0
            if cropY < 0:  # There is a bug with cropperjs. y can be negative.
                cropY = 0
            crop_img = img[cropY:cropY+cropHeight, cropX:cropX+cropWidth]

            cv2.imwrite(url, crop_img)

            # delete the old image
            user.profile_image.delete()

            # Save the cropped image to user model
            user.profile_image.save(
                "profile_image.png", files.File(open(url, 'rb')))
            user.save()

            payload['result'] = "success"
            payload['cropped_profile_image'] = user.profile_image.url

            # delete temp file
            os.remove(url)
        except Exception as e:
            print("exception: " + str(e))
            payload['result'] = "error"
            payload['exception'] = str(e)

    return HttpResponse(json.dumps(payload), content_type="application/json")


def report(request):
    print(request.GET)
    data = {}
    data['form'] = RelatoForm()
    # Create MAp
    m = folium.Map(location=[-26.900420999510086, -
                   49.08161133527756], zoom_start=15)
    folium.Marker(location=[-26.900420999510086, -49.08161133527756],
                  tooltop='clique para mais', popup='Centro POP').add_to(m)
    # Get html representation of map
    m = m._repr_html_()
    data['map'] = m
    return render(request, 'pages/report.html', data)


def create(request):
    if request.method == "POST":
        form = RelatoForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect('index')


def dashboard(request):
    list_relatos = Relato.objects.order_by('id')
    myFilter = RelatoFilter(request.GET, queryset=list_relatos)
    list_relatos = myFilter.qs
    paginator = Paginator(list_relatos, 10)
    page = request.GET.get('page')
    list_relatos = paginator.get_page(page)
    return render(request, 'pages/dashboard.html', {'relatos': list_relatos, 'myFilter': myFilter})


def detail(request, pk):
    relato = Relato.objects.get(pk=pk)
    return render(request, 'pages/detalhe.html', {'relato': relato})


def edit(request, pk):
    relato = Relato.objects.get(pk=pk)
    form = RelatoForm(instance=relato)
    return render(request, 'pages/edit.html', {'relato': relato, 'form': form})


def update(request, pk):
    relato = Relato.objects.get(pk=pk)
    form = RelatoForm(request.POST, instance=relato)
    if form.is_valid():
        form.save()
        return redirect('dashboard')


def delete(request, pk):
    relato = Relato.objects.get(pk=pk)
    relato.delete()
    return redirect('dashboard')


def dados(request):
    list_relatos = Relato.objects.filter(categoria="2")
    return render(request, 'pages/public_dashboard.html', {'relatos': list_relatos})
