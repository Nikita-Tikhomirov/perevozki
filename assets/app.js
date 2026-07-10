const header = document.querySelector("[data-site-header]");
const menuToggle = document.querySelector("[data-menu-toggle]");
const mainNav = document.querySelector("[data-main-nav]");
const form = document.querySelector("[data-demo-form]");
const formButton = document.querySelector("[data-demo-submit]");
const formStatus = document.querySelector("[data-form-status]");

if (header && menuToggle && mainNav) {
  const closeMenu = () => {
    header.removeAttribute("data-menu-open");
    menuToggle.setAttribute("aria-expanded", "false");
    menuToggle.setAttribute("aria-label", "Открыть меню");
  };

  menuToggle.addEventListener("click", () => {
    const open = header.toggleAttribute("data-menu-open");
    menuToggle.setAttribute("aria-expanded", String(open));
    menuToggle.setAttribute(
      "aria-label",
      open ? "Закрыть меню" : "Открыть меню",
    );
  });

  mainNav.addEventListener("click", (event) => {
    if (event.target.closest("a")) {
      closeMenu();
    }
  });

  window.addEventListener("resize", () => {
    if (window.innerWidth > 900) {
      closeMenu();
    }
  });
}

if (form && formButton && formStatus) {
  formButton.addEventListener("click", () => {
    const nameField = form.querySelector('input[name="name"]');
    const phoneField = form.querySelector('input[name="phone"]');
    const phoneDigits = phoneField.value.replace(/\D/g, "");
    const nameIsValid = nameField.value.trim().length >= 2;
    const phoneIsValid = phoneDigits.length >= 9;

    nameField.setAttribute("aria-invalid", String(!nameIsValid));
    phoneField.setAttribute("aria-invalid", String(!phoneIsValid));

    if (!nameIsValid || phoneDigits.length < 9) {
      formStatus.textContent = "Укажите имя и телефон минимум из 9 цифр.";
      (nameIsValid ? phoneField : nameField).focus();
      return;
    }

    formStatus.textContent =
      "Заявка заполнена — позвоните или напишите нам для точного расчёта.";
  });
}
