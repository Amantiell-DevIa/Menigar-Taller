/**
 * MENIGAR DESARROLLOS DIGITALES - LOGIC & INTERACTIVITY
 * High-Tech Automotive Diagnostic & Quote Engine
 */

document.addEventListener('DOMContentLoaded', () => {
  initGoogleDynamicIsland();
  initSmartVehicleFinder();
  initDtcSearchEngine();
  initTopRepairFilters();
  initReviewsFilter();
  initModalAndForms();
  initMobileNavigation();
  initAccessibility();
});

/* ==========================================================================
   1. NOTIFICACIÓN FLOTANTE DYNAMIC ISLAND (RESEÑAS GOOGLE)
   ========================================================================== */
function initGoogleDynamicIsland() {
  const island = document.getElementById('googleIslandBadge');
  if (!island) return;

  let hasTriggered = false;
  let hideTimer = null;

  const showIsland = () => {
    island.classList.add('is-visible');
    
    // Limpiar temporizador previo si lo hubiera
    if (hideTimer) clearTimeout(hideTimer);
    
    // Mantener flotante en la pantalla durante 4 segundos y luego ocultar suavemente
    hideTimer = setTimeout(() => {
      island.classList.remove('is-visible');
    }, 4000);
  };

  const handleScroll = () => {
    const scrollPos = window.scrollY || document.documentElement.scrollTop;

    // Se activa al hacer un poco de scroll (más de 60px)
    if (scrollPos > 60 && !hasTriggered) {
      hasTriggered = true;
      showIsland();
    } else if (scrollPos < 20) {
      // Si el usuario vuelve a la parte superior de la web, reseteamos el trigger
      // para que al bajar de nuevo vuelva a verse la animación
      hasTriggered = false;
    }
  };

  window.addEventListener('scroll', handleScroll, { passive: true });

  // Si el usuario hace clic o pulsa en el pill, navega a opiniones y oculta la isla
  island.addEventListener('click', () => {
    if (hideTimer) clearTimeout(hideTimer);
    island.classList.remove('is-visible');
  });
}

/* ==========================================================================
   2. SMART VEHICLE & FAULT FINDER (SELECTOR EN 3 CLICS)
   ========================================================================== */
const VEHICLE_DATABASE = {
  abs: {
    name: 'Módulo y Bomba de ABS / ESP',
    brands: {
      bmw: {
        name: 'BMW',
        models: [
          {
            id: 'bmw-s1',
            name: 'Serie 1 (E81, E87, F20) 2004-2016',
            title: 'Reparación Módulo ABS BMW Serie 1 (ATE MK60 / MK61 / MK100)',
            desc: 'Testigos de ABS, DSC y freno de mano encendidos en amarillo. Fallo recurrente en sensor de presión interno o motor de la bomba de retorno. Reparación electrónica completa sin cambiar la bomba.',
            lights: ['abs', 'esp', 'brake'],
            codes: ['5DF5 (Fallo Unidad)', '5DF0 (Motor Bomba)', '5E20 (Sensor Presión)']
          },
          {
            id: 'bmw-s3',
            name: 'Serie 3 (E46, E90, E91, E92, F30) 1998-2016',
            title: 'Reparación Centralita y Bomba ABS BMW Serie 3',
            desc: 'Avería clásica de la unidad hidráulica ATE MK60 y MK61. Se desactiva el control de estabilidad DSC. Reparación en 24h con sustitución de componentes electrónicos reforzados.',
            lights: ['abs', 'esp', 'brake'],
            codes: ['5DF5', '5DF0', '5E20', '5DF1']
          },
          {
            id: 'bmw-s5',
            name: 'Serie 5 (E39, E60, F10) / X5',
            title: 'Reparación ABS Bosch 5.7 / DSC BMW Serie 5 y X5',
            desc: 'Fallo al calentarse el motor: los velocímetros fallan o se encienden 3 luces en el cuadro. Reparación de pistas microscópicas de conexión híbrida.',
            lights: ['abs', 'esp', 'brake'],
            codes: ['Error Sensor Rueda', 'Fallo Relé Válvulas', 'Fallo Comunicación CAN']
          },
          {
            id: 'bmw-moto',
            name: 'BMW Motorrad (Motos R1200GS, F800, etc.)',
            title: 'Reparación Módulo ABS Integral FTE / ATE para Motos BMW',
            desc: 'Fallo del servofreno o motor de bomba de ABS en motocicletas BMW. Reparamos la unidad completa evitando los más de 2.000€ que cuesta en concesionario.',
            lights: ['abs', 'brake'],
            codes: ['Fallo Motor Bomba', 'Presión Insuficiente', 'Fallo Modulador']
          }
        ]
      },
      vag: {
        name: 'Volkswagen / Audi / Seat / Skoda',
        models: [
          {
            id: 'vag-mk60',
            name: 'Golf V / VI, León II, A3 8P, Octavia (ATE MK60 / MK60EC1)',
            title: 'Reparación ABS ATE MK60 y MK60EC1 Grupo VAG',
            desc: 'Fallo masivo de sensor de presión de frenado G201 o centralita electrónica defectuosa. Testigos de ABS y ESP fijos en el cuadro. Reparación garantizada por 2 años.',
            lights: ['abs', 'esp', 'brake'],
            codes: ['01435 (Sensor G201)', '01130 (Señal no plausible)', '16352 (Unidad Defectuosa)']
          },
          {
            id: 'vag-mk100',
            name: 'Golf VII, Polo, Ibiza, A1, Fabia (ATE MK100)',
            title: 'Reparación Módulo ABS ATE MK100 Grupo VAG',
            desc: 'Pérdida de comunicación con el módulo de freno o fallo interno en la memoria EEPROM. Reparación y prueba en 24h en nuestro taller.',
            lights: ['abs', 'esp'],
            codes: ['01276 (Bomba V64)', 'DTC402012', 'Error Comunicación']
          }
        ]
      },
      renault: {
        name: 'Renault',
        models: [
          {
            id: 'renault-abs-mk60',
            name: 'Megane II, Scénic II, Laguna II, Clio III',
            title: 'Reparación Módulo ABS ATE MK60 Renault',
            desc: 'Avería interna del sensor de presión hidráulico o relé de alimentación de bomba. Mensaje "Revisar ABS / ESP" en la pantalla de abordo.',
            lights: ['abs', 'esp'],
            codes: ['DF088 (Sensor Presión)', 'DF010', 'DF017']
          }
        ]
      },
      mercedes: {
        name: 'Mercedes-Benz',
        models: [
          {
            id: 'mb-sbc',
            name: 'Clase E (W211), Clase SL (R230), CLS (W219) - Módulo SBC',
            title: 'Reparación Unidad de Freno Electrohidráulico SBC Mercedes',
            desc: 'Aviso en rojo en el cuadro: "Freno: ¡Detenga el vehículo!". Límite de ciclo de pisadas alcanzado o pérdida de presión acumulador.',
            lights: ['brake', 'abs'],
            codes: ['C249F (Vida Útil)', 'C233D', 'C223D', 'C2131']
          }
        ]
      },
      citroen: {
        name: 'Citroën / Peugeot',
        models: [
          {
            id: 'psa-mk70',
            name: 'C2, C3, C4, 206, 207, 307 (ATE MK70)',
            title: 'Reparación Módulo ABS ATE MK70 PSA',
            desc: 'El fallo más común del grupo francés: fallo de alimentación del motor de bomba de recirculación de ABS.',
            lights: ['abs'],
            codes: ['C1380 (Fallo Motor Bomba)', 'C1350', 'C1301']
          }
        ]
      }
    }
  },
  cuadro: {
    name: 'Cuadros de Instrumentos y Odómetros',
    brands: {
      renault: {
        name: 'Renault',
        models: [
          {
            id: 'scenic2',
            name: 'Scénic II y Grand Scénic (2003-2009)',
            title: 'Reparación Cuadro Digital Renault Scénic II',
            desc: 'El cuadro se apaga por completo, parpadea intermitentemente, se desprograma la hora o suma kilómetros de forma errónea. Sustituimos transformador de alimentación, transistores MOSFET y resistencias reforzadas.',
            lights: ['engine'],
            codes: ['Fallo Alimentación VFD', 'Pérdida de Kilometraje Parcial']
          },
          {
            id: 'megane3',
            name: 'Megane III y Laguna III',
            title: 'Reparación Iluminación y Pantalla Renault Megane 3',
            desc: 'Fallo de la iluminación en el velocímetro digital o cuadro analógico apagado.',
            lights: [],
            codes: ['Fallo Retroiluminación LED', 'Microprocesador']
          }
        ]
      },
      ford: {
        name: 'Ford',
        models: [
          {
            id: 'focus2',
            name: 'Focus II y C-MAX (2004-2011)',
            title: 'Reparación Cuadro de Instrumentos Ford Focus II',
            desc: 'Síntomas: El coche se para en marcha o no arranca, parpadea el testigo rojo del inmovilizador, agujas se caen a cero y en el display aparece "Fallo motor". Causado por grietas en soldaduras del conector principal.',
            lights: ['engine', 'brake'],
            codes: ['U1900 (Fallo Bus CAN)', 'U0155', 'P1260 (Inmovilizador)']
          }
        ]
      },
      psa_fiat: {
        name: 'Citroën / Fiat / Peugeot Industriales',
        models: [
          {
            id: 'odometro-399999',
            name: 'Ducato, Jumper, Boxer (2006-2020)',
            title: 'Reparación Fallo Cuentakilómetros Bloqueado en 399.999 km',
            desc: 'El odómetro alcanza los 399.999 km y se bloquea permanentemente mostrando guiones o parpadeo, impidiendo superar la inspección técnica ITV. Desbloqueo y ajuste exacto en 24h.',
            lights: [],
            codes: ['Bloqueo EEPROM 399.999km', 'Fallo Display LCD']
          }
        ]
      },
      vag: {
        name: 'Audi / Seat / VW / Skoda',
        models: [
          {
            id: 'vag-luz',
            name: 'Golf V, León II, A3 8P, Octavia',
            title: 'Reparación Fallo Iluminación Cuadros VAG',
            desc: 'Las agujas o las esferas no se iluminan, parpadean o se quedan en penumbra de noche. Cambio de líneas LED y controladores de potencia.',
            lights: [],
            codes: ['Fallo Driver Iluminación', 'Fallo Display FIS']
          }
        ]
      },
      nissan: {
        name: 'Nissan',
        models: [
          {
            id: 'nissan-oil',
            name: 'Atleon, Cabstar, Interstar, Terrano',
            title: 'Reparación Fallo Mensaje "OIL" en Display Nissan',
            desc: 'Mensaje permanente "OIL" en el display digital a pesar de tener el nivel de aceite correcto y resetear el servicio.',
            lights: ['engine'],
            codes: ['Aviso Falso Nivel Aceite', 'Corrupción Datos Memoria']
          }
        ]
      }
    }
  },
  multimedia: {
    name: 'Pantallas Táctiles y Multimedia',
    brands: {
      hyundai: {
        name: 'Hyundai / Kia',
        models: [
          {
            id: 'tucson-burbujas',
            name: 'Tucson (2015-2021) y Sportage',
            title: 'Reparación de Burbujas en Pantalla Táctil Hyundai Tucson',
            desc: 'Aparición de burbujas de aire y pegamento derretido en la pantalla táctil de 8", perdiendo respuesta al tocarla. Sustituimos el digitalizador por uno nuevo reforzado que nunca vuelve a crear burbujas.',
            lights: [],
            codes: ['Fallo Adhesivo Óptico LOCA', 'Pulsaciones Fantasma']
          }
        ]
      },
      bmw: {
        name: 'BMW / Mini',
        models: [
          {
            id: 'bmw-puntos-negros',
            name: 'Serie 1, Serie 3, Mini Cooper (Pantalla 6.5" y 8.8")',
            title: 'Reparación de Puntos Negros en Pantallas BMW y Mini',
            desc: 'Manchas negras circulares que crecen y tapan la información de navegación o radio. Reemplazo del panel LCD original.',
            lights: [],
            codes: ['Fuga Cristales Líquidos', 'Mancha Negra Central']
          }
        ]
      },
      opel: {
        name: 'Opel',
        models: [
          {
            id: 'opel-intellilink',
            name: 'Astra K, Insignia (Navi Pro 39042448)',
            title: 'Reparación Pantalla IntelliLink Opel Ref. 39042448',
            desc: 'La pantalla se queda negra, se congela el logotipo de Opel o el táctil deja de responder.',
            lights: [],
            codes: ['Fallo Módulo HMI', 'Fallo Display LCD']
          }
        ]
      },
      vag: {
        name: 'Volkswagen / Seat / Skoda',
        models: [
          {
            id: 'vw-composition',
            name: 'Golf VII, Polo, Tiguan (Composition / Discover Media)',
            title: 'Reparación Pantalla Táctil VW Composition Media',
            desc: 'La pantalla cambia sola de emisora ("toques fantasma") o la mitad de la pantalla no responde al pulsar.',
            lights: [],
            codes: ['Descalibración Digitalizador', 'Fallo Cristal Táctil']
          }
        ]
      }
    }
  },
  display: {
    name: 'Displays LCD y Cuentakilómetros',
    brands: {
      mercedes: {
        name: 'Mercedes-Benz',
        models: [
          {
            id: 'mb-vito',
            name: 'Vito, Viano (W639), Clase A (W169), Clase B',
            title: 'Reparación Display Central Mercedes Vito y Viano',
            desc: 'El display LCD del cuentakilómetros se va apagando y pierde contraste a medida que el coche se calienta. Sustitución de pantalla por una de alta definición.',
            lights: [],
            codes: ['Fallo Tira Plana / Flex Display']
          }
        ]
      },
      vag: {
        name: 'Audi / VW',
        models: [
          {
            id: 'vag-fis',
            name: 'Audi A3, A4, A6, Golf IV (Pantalla FIS)',
            title: 'Reparación Display FIS / MFA Grupo VAG',
            desc: 'Líneas horizontales o verticales muertas, pérdida de píxeles que impiden ver el consumo o los avisos de avería.',
            lights: [],
            codes: ['Pérdida de Píxeles LCD']
          }
        ]
      }
    }
  },
  cambio: {
    name: 'Electrónica de Cambio Automático',
    brands: {
      vag: {
        name: 'Volkswagen / Audi / Seat / Skoda',
        models: [
          {
            id: 'dsg-mechatronic',
            name: 'Cajas DSG 6 (DQ250) y DSG 7 (DQ200)',
            title: 'Reparación Mecatrónica y Centralita DSG',
            desc: 'El cambio da tirones, no entran las marchas pares o impares, o parpadea la llave inglesa/letra PRNDS en el cuadro. Reparación de placas y solenoides.',
            lights: ['engine', 'brake'],
            codes: ['P17BF (Protección de Bomba)', 'P189C (Presión Insuficiente)', 'P0706']
          }
        ]
      },
      opel: {
        name: 'Opel',
        models: [
          {
            id: 'easytronic-f',
            name: 'Corsa C/D, Meriva, Astra H (Easytronic)',
            title: 'Reparación Módulo de Embrague y Cambio Easytronic',
            desc: 'Aparece la letra "F" en el cuadro y el coche no arranca. Reparación electrónica del actuador de embrague y motor eléctrico.',
            lights: ['engine'],
            codes: ['Fallo Letra F', 'P1607 (Error Actuador Embrague)', 'P1700']
          }
        ]
      },
      mercedes: {
        name: 'Mercedes-Benz',
        models: [
          {
            id: '7g-tronic',
            name: 'Cajas 7G-Tronic (722.9)',
            title: 'Reparación Placa Electrónica de Cambio 7G-Tronic',
            desc: 'El cambio se bloquea en una marcha de emergencia (limp mode). Avería recurrente de los sensores de velocidad internos Y3/8n1 y Y3/8n2.',
            lights: ['engine'],
            codes: ['0717 (Señal RPM Y3/8n1)', '0718', '2767', '2768']
          }
        ]
      }
    }
  },
  ecu: {
    name: 'Centralita de Motor ECU',
    brands: {
      opel: {
        name: 'Opel',
        models: [
          {
            id: 'isuzu-17',
            name: 'Astra, Corsa, Meriva 1.7 DTi (Isuzu)',
            title: 'Reparación Centralita Bomba Inyección Opel 1.7 DTi (Delphi / Isuzu)',
            desc: 'El coche se para en caliente y no arranca hasta que se enfría. Soldaduras rotas y componentes térmicos degradados. Modificación y refuerzo.',
            lights: ['engine'],
            codes: ['P0251 (Fallo Válvula Dosificación Bomba)', 'P0370']
          }
        ]
      }
    }
  },
  bsi: {
    name: 'Unidad BSI / Confort',
    brands: {
      psa: {
        name: 'Peugeot / Citroën',
        models: [
          {
            id: 'psa-bsi',
            name: '206, 207, 307, 407, Xsara, Picasso, C4',
            title: 'Reparación Unidad BSI Peugeot y Citroën',
            desc: 'Fallos inexplicables: limpiaparabrisas se activan solos, fallo de luces, cierre centralizado no abre o descarga de batería.',
            lights: ['engine'],
            codes: ['Fallo Red Multiplexada VAN/CAN', 'Relé Cierre Quemado']
          }
        ]
      }
    }
  },
  inmo: {
    name: 'Inmovilizador & Blue&Me',
    brands: {
      fiat: {
        name: 'Fiat / Alfa Romeo / Lancia',
        models: [
          {
            id: 'blue-and-me',
            name: 'Fiat 500, Punto, Bravo, Giulietta, Mito',
            title: 'Reparación Centralita Bluetooth Blue&Me Fiat',
            desc: 'Cuentakilómetros total parpadea continuamente, no conecta el teléfono por Bluetooth o descarga completamente la batería del coche en 24 horas.',
            lights: [],
            codes: ['Consumo de Batería 0.3A en reposo', 'Odómetro Parpadeando']
          }
        ]
      }
    }
  }
};

function initSmartVehicleFinder() {
  const compSelect = document.getElementById('componentSelect');
  const brandSelect = document.getElementById('brandSelect');
  const modelSelect = document.getElementById('modelSelect');
  const findBtn = document.getElementById('findFixBtn');
  const form = document.getElementById('vehicleFinderForm');
  const resultPanel = document.getElementById('finderResult');

  // Tabs & contenedores de modo
  const tabSymptoms = document.getElementById('tabModeSymptoms');
  const tabComponent = document.getElementById('tabModeComponent');
  const tabDtc = document.getElementById('tabModeDtc');
  const symptomsContainer = document.getElementById('symptomsModeContainer');
  const dtcContainer = document.getElementById('dtcModeContainer');
  const symptomCards = document.querySelectorAll('.symptom-card[data-comp]');
  const btnHelpUnknown = document.getElementById('btnHelpUnknown');

  // Función de conmutación de modos
  window.setFinderMode = function(mode) {
    if (tabSymptoms) {
      tabSymptoms.classList.toggle('active', mode === 'symptoms');
      tabSymptoms.setAttribute('aria-selected', mode === 'symptoms');
    }
    if (tabComponent) {
      tabComponent.classList.toggle('active', mode === 'component');
      tabComponent.setAttribute('aria-selected', mode === 'component');
    }
    if (tabDtc) {
      tabDtc.classList.toggle('active', mode === 'dtc');
      tabDtc.setAttribute('aria-selected', mode === 'dtc');
    }

    if (mode === 'symptoms') {
      if (symptomsContainer) symptomsContainer.style.display = 'block';
      if (form) form.style.display = 'grid';
      if (dtcContainer) dtcContainer.style.display = 'none';
    } else if (mode === 'component') {
      if (symptomsContainer) symptomsContainer.style.display = 'none';
      if (form) form.style.display = 'grid';
      if (dtcContainer) dtcContainer.style.display = 'none';
      if (compSelect) compSelect.focus();
    } else if (mode === 'dtc') {
      if (symptomsContainer) symptomsContainer.style.display = 'none';
      if (form) form.style.display = 'none';
      if (dtcContainer) dtcContainer.style.display = 'block';
      const dtcInput = document.getElementById('dtcInput');
      if (dtcInput) dtcInput.focus();
    }
  };

  if (tabSymptoms) tabSymptoms.addEventListener('click', () => window.setFinderMode('symptoms'));
  if (tabComponent) tabComponent.addEventListener('click', () => window.setFinderMode('component'));
  if (tabDtc) tabDtc.addEventListener('click', () => window.setFinderMode('dtc'));

  // Clic en tarjetas de síntomas
  symptomCards.forEach(card => {
    card.addEventListener('click', () => {
      symptomCards.forEach(c => c.classList.remove('active'));
      card.classList.add('active');
      const compVal = card.getAttribute('data-comp');
      if (compSelect && compVal) {
        compSelect.value = compVal;
        compSelect.dispatchEvent(new Event('change'));
        if (brandSelect && !brandSelect.disabled) {
          brandSelect.focus();
        }
      }
    });
  });

  // Botón "¿No sabes qué le pasa?"
  if (btnHelpUnknown) {
    btnHelpUnknown.addEventListener('click', () => {
      openQuoteModalWith({
        component: 'Diagnóstico de Avería No Identificada',
        symptoms: 'Necesito que un técnico de Menigar me ayude a diagnosticar el problema de mi vehículo.'
      });
    });
  }

  if (!compSelect || !brandSelect || !modelSelect) return;

  // Paso 1: Cambia componente
  compSelect.addEventListener('change', () => {
    const compVal = compSelect.value;
    brandSelect.innerHTML = '<option value="">Selecciona la marca...</option>';
    modelSelect.innerHTML = '<option value="">Primero elige marca...</option>';
    brandSelect.disabled = true;
    modelSelect.disabled = true;
    findBtn.disabled = true;
    resultPanel.style.display = 'none';

    // Sincronizar tarjeta de síntoma activa si existe
    symptomCards.forEach(c => {
      c.classList.toggle('active', c.getAttribute('data-comp') === compVal);
    });

    if (compVal && VEHICLE_DATABASE[compVal]) {
      const brands = VEHICLE_DATABASE[compVal].brands;
      Object.keys(brands).forEach(bKey => {
        const opt = document.createElement('option');
        opt.value = bKey;
        opt.textContent = brands[bKey].name;
        brandSelect.appendChild(opt);
      });
      brandSelect.disabled = false;
    }
  });

  // Paso 2: Cambia marca
  brandSelect.addEventListener('change', () => {
    const compVal = compSelect.value;
    const brandVal = brandSelect.value;
    modelSelect.innerHTML = '<option value="">Selecciona el modelo...</option>';
    modelSelect.disabled = true;
    findBtn.disabled = true;
    resultPanel.style.display = 'none';

    if (compVal && brandVal && VEHICLE_DATABASE[compVal]?.brands[brandVal]) {
      const models = VEHICLE_DATABASE[compVal].brands[brandVal].models;
      models.forEach(m => {
        const opt = document.createElement('option');
        opt.value = m.id;
        opt.textContent = m.name;
        modelSelect.appendChild(opt);
      });
      modelSelect.disabled = false;
    }
  });

  // Paso 3: Cambia modelo
  modelSelect.addEventListener('change', () => {
    findBtn.disabled = !modelSelect.value;
  });

  // Submit del Finder
  form.addEventListener('submit', (e) => {
    e.preventDefault();
    const compVal = compSelect.value;
    const brandVal = brandSelect.value;
    const modelVal = modelSelect.value;

    if (!compVal || !brandVal || !modelVal) return;

    const brandData = VEHICLE_DATABASE[compVal]?.brands[brandVal];
    const modelData = brandData?.models.find(m => m.id === modelVal);

    if (!modelData) return;

    // Inyectar datos en el resultado
    document.getElementById('resTitle').textContent = modelData.title;
    document.getElementById('resDesc').textContent = modelData.desc;

    // Inyectar Testigos Luminosos
    const lightsWrap = document.getElementById('resLights');
    lightsWrap.innerHTML = '';
    if (modelData.lights && modelData.lights.length > 0) {
      modelData.lights.forEach(l => {
        const badge = document.createElement('div');
        badge.className = `dash-light ${l === 'brake' ? 'red' : 'amber'}`;
        if (l === 'abs') badge.innerHTML = 'ABS';
        else if (l === 'esp') badge.innerHTML = 'ESP';
        else if (l === 'brake') badge.innerHTML = '(!)';
        else if (l === 'engine') badge.innerHTML = 'MIL';
        lightsWrap.appendChild(badge);
      });
    } else {
      lightsWrap.innerHTML = '<span style="font-size:0.85rem; color:#94a3b8;">Fallo visible en pantalla/iluminación</span>';
    }

    // Inyectar Códigos de error
    const codesWrap = document.getElementById('resCodes');
    codesWrap.innerHTML = '';
    modelData.codes.forEach(c => {
      const pill = document.createElement('span');
      pill.className = 'code-pill';
      pill.textContent = c;
      codesWrap.appendChild(pill);
    });

    // Configurar botones de CTA
    const quoteBtn = document.getElementById('quoteDirectBtn');
    quoteBtn.onclick = () => {
      openQuoteModalWith({
        vehicle: `${brandData.name} - ${modelData.name}`,
        component: VEHICLE_DATABASE[compVal].name,
        symptoms: `${modelData.title}. Síntomas: ${modelData.desc}`
      });
    };

    const waBtn = document.getElementById('whatsappDirectBtn');
    const waText = encodeURIComponent(`Hola Menigar, consulto por la reparación de: ${modelData.title} (${brandData.name}). ¿Tenéis disponibilidad para recogida?`);
    waBtn.href = `https://wa.me/34916622781?text=${waText}`;

    // Mostrar panel
    resultPanel.style.display = 'block';
    resultPanel.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
  });
}

// Función global para abrir el Finder preseleccionando un componente
window.openFinderWith = function(compKey) {
  const compSelect = document.getElementById('componentSelect');
  const finderElem = document.getElementById('buscador-averias');
  
  if (typeof window.setFinderMode === 'function') {
    window.setFinderMode('symptoms');
  }

  const symptomCards = document.querySelectorAll('.symptom-card[data-comp]');
  symptomCards.forEach(c => {
    c.classList.toggle('active', c.getAttribute('data-comp') === compKey);
  });

  if (compSelect && finderElem) {
    compSelect.value = compKey;
    compSelect.dispatchEvent(new Event('change'));
    finderElem.scrollIntoView({ behavior: 'smooth' });
  }
};

/* ==========================================================================
   3. DTC / OBD ERROR CODE SEARCH ENGINE
   ========================================================================== */
const DTC_DATABASE = {
  '5DF5': {
    code: '5DF5',
    title: 'BMW Módulo ABS (ATE MK60 / MK61) - Fallo Interno Centralita',
    desc: 'Error crítico en memoria y procesador de la unidad de mando ABS en BMW Serie 1 (E87), Serie 3 (E90), Z4. Reparación garantizada 2 años en 24h.'
  },
  '01130': {
    code: '01130',
    title: 'Grupo VAG (VW, Seat, Skoda, Audi) - ABS Funcionamiento no Plausible',
    desc: 'Aparece en Golf V, León II, Octavia. Módulo hidráulico pierde calibración de presión o fallo de comunicación. Reparación completa garantizada.'
  },
  'C1380': {
    code: 'C1380',
    title: 'Citroën / Peugeot (ATE MK70) - Fallo Motor Bomba de Recirculación',
    desc: 'Avería habitual en C3, C4, 207, 307. Bloqueo de alimentación del motor eléctrico de ABS. Sustitución de electrónica de potencia reforzada.'
  },
  '16352': {
    code: '16352',
    title: 'Grupo VAG - Módulo de Control Eléctrico Defectuoso',
    desc: 'Avería de hardware en centralita electrónica de frenado o confort. Reparamos el componente original sin codificar nada.'
  },
  '399999': {
    code: '399.999 km',
    title: 'Furgonetas Citroën Jumper / Fiat Ducato / Peugeot Boxer - Cuentakilómetros Parado',
    desc: 'El odómetro digital se detiene al llegar a 399.999 km e impide pasar la ITV. Desbloqueo y ajuste exacto en 24h.'
  },
  'OIL': {
    code: 'Aviso OIL',
    title: 'Nissan Industriales (Atleon, Cabstar, Interstar) - Mensaje OIL en Display',
    desc: 'El cuadro marca aviso de aceite de manera fija debido a una corrupción en el procesador. Reparación en taller en 24h.'
  },
  '01276': {
    code: '01276',
    title: 'Grupo VAG - Bomba Hidráulica de ABS (V64)',
    desc: 'Fallo de alimentación o circuito abierto en la bomba hidráulica de ABS. Reparación de motor y conexiones internas.'
  },
  '01435': {
    code: '01435',
    title: 'Grupo VAG - Transmisor 1 Presión de Frenado (G201)',
    desc: 'El sensor piezoeléctrico de presión interna de la bomba ATE MK60 falla. Reparamos el bloque sustituyendo el transductor por uno nuevo.'
  },
  '5DF0': {
    code: '5DF0',
    title: 'BMW ABS - Fallo Motor de la Bomba Hidráulica',
    desc: 'Desgaste prematuro de escobillas del motor o gripaje de rodamientos de la bomba ATE MK60/MK61.'
  },
  '5E20': {
    code: '5E20',
    title: 'BMW ABS - Sensor de Presión de Freno 1 Defectuoso',
    desc: 'Fallo en la lectura de bares de presión del circuito de freno. Solución en menos de 24h.'
  },
  'C1288': {
    code: 'C1288',
    title: 'Ford / Mazda - Transductor de Presión de Freno Primario',
    desc: 'Avería recurrente en Ford Focus II, C-MAX y Mazda 3 con módulo ABS ATE MK60.'
  },
  'DF088': {
    code: 'DF088',
    title: 'Renault - Circuito del Sensor de Presión de Frenado',
    desc: 'Fallo en Scénic II y Megane II. Sustitución de unidad de lectura de presión de freno.'
  }
};

function initDtcSearchEngine() {
  const dtcInput = document.getElementById('dtcInput');
  const searchBtn = document.getElementById('searchDtcBtn');
  const resultBox = document.getElementById('dtcResultBox');
  const resTitle = document.getElementById('dtcResultTitle');
  const resDesc = document.getElementById('dtcResultDesc');
  const quoteBtn = document.getElementById('dtcQuoteBtn');
  const closeBtn = document.getElementById('closeDtcBtn');
  const chips = document.querySelectorAll('.dtc-chip');

  if (!dtcInput || !searchBtn || !resultBox) return;

  function executeSearch(query) {
    const cleanQuery = query.trim().toUpperCase().replace('.', '');
    if (!cleanQuery) return;

    // Buscar coincidencia exacta o parcial
    let match = null;
    for (let key in DTC_DATABASE) {
      if (cleanQuery.includes(key) || key.includes(cleanQuery)) {
        match = DTC_DATABASE[key];
        break;
      }
    }

    if (match) {
      resTitle.textContent = `Código ${match.code}: ${match.title}`;
      resDesc.textContent = match.desc;
      quoteBtn.onclick = () => {
        openQuoteModalWith({
          component: 'Diagnóstico por Código de Error',
          symptoms: `Avería diagnosticada por código: ${match.code} - ${match.title}`
        });
      };
      resultBox.style.display = 'block';
    } else {
      resTitle.textContent = `Código "${query}" registrado`;
      resDesc.textContent = `Reparamos este código de avería en nuestro taller. Consúltanos con la referencia de tu centralita para confirmar disponibilidad en 24h.`;
      quoteBtn.onclick = () => {
        openQuoteModalWith({
          component: 'Código de Error ' + query,
          symptoms: `Diagnóstico máquina: código de error ${query}`
        });
      };
      resultBox.style.display = 'block';
    }
  }

  searchBtn.addEventListener('click', () => executeSearch(dtcInput.value));
  dtcInput.addEventListener('keypress', (e) => {
    if (e.key === 'Enter') {
      e.preventDefault();
      executeSearch(dtcInput.value);
    }
  });

  chips.forEach(chip => {
    chip.addEventListener('click', () => {
      const code = chip.getAttribute('data-code');
      dtcInput.value = code;
      executeSearch(code);
    });
  });

  closeBtn.addEventListener('click', () => {
    resultBox.style.display = 'none';
  });
}

/* ==========================================================================
   4. TOP REPAIR FILTERS
   ========================================================================== */
function initTopRepairFilters() {
  const filterBtns = document.querySelectorAll('.filter-btn');
  const repairItems = document.querySelectorAll('.repair-item');

  if (!filterBtns.length || !repairItems.length) return;

  filterBtns.forEach(btn => {
    btn.addEventListener('click', () => {
      filterBtns.forEach(b => b.classList.remove('active'));
      btn.classList.add('active');

      const filter = btn.getAttribute('data-filter');

      repairItems.forEach(item => {
        const category = item.getAttribute('data-category');
        if (filter === 'all' || category === filter) {
          item.style.display = 'flex';
          item.style.animation = 'fadeIn 0.3s ease';
        } else {
          item.style.display = 'none';
        }
      });
    });
  });
}

// Función global para solicitar presupuesto de una Top Repair
window.requestSpecificRepair = function(repairTitle) {
  openQuoteModalWith({
    component: repairTitle,
    symptoms: `Solicitud de presupuesto y recogida urgente 24h para la reparación: ${repairTitle}`
  });
};

/* ==========================================================================
   5. MODAL INTERACTIVO & FORMULARIOS DE PRESUPUESTO
   ========================================================================== */
const modal = document.getElementById('quoteModal');
const openModalBtn = document.getElementById('openQuoteModalBtn');
const closeModalBtn = document.getElementById('closeModalBtn');
const modalForm = document.getElementById('modalQuoteForm');
const mainForm = document.getElementById('mainQuoteForm');
const toast = document.getElementById('toastMessage');

function showToast(msg) {
  if (!toast) return;
  toast.textContent = msg;
  toast.classList.add('show');
  setTimeout(() => {
    toast.classList.remove('show');
  }, 4500);
}

function openQuoteModalWith(data = {}) {
  if (!modal) return;
  if (data.vehicle) {
    const input = document.getElementById('mVehicle');
    if (input) input.value = data.vehicle;
  }
  if (data.component) {
    const input = document.getElementById('mComponent');
    if (input) input.value = data.component;
  }
  if (data.symptoms) {
    const input = document.getElementById('mSymptoms');
    if (input) input.value = data.symptoms;
  }
  modal.classList.add('active');
}

function initModalAndForms() {
  if (openModalBtn && modal) {
    openModalBtn.addEventListener('click', () => {
      modal.classList.add('active');
    });
  }

  if (closeModalBtn && modal) {
    closeModalBtn.addEventListener('click', () => {
      modal.classList.remove('active');
    });
  }

  if (modal) {
    modal.addEventListener('click', (e) => {
      if (e.target === modal) modal.classList.remove('active');
    });
  }

  // Submit Modal Form
  if (modalForm) {
    modalForm.addEventListener('submit', (e) => {
      e.preventDefault();
      modal.classList.remove('active');
      modalForm.reset();
      showToast('✓ ¡Solicitud enviada con éxito! Un técnico de Menigar te llamará en menos de 2 horas.');
    });
  }

  // Submit Main Contact Form
  if (mainForm) {
    mainForm.addEventListener('submit', (e) => {
      e.preventDefault();
      mainForm.reset();
      showToast('✓ ¡Solicitud de presupuesto recibida! Revisamos la referencia de tu pieza y te contactamos.');
    });
  }
}

/* ==========================================================================
   6. NAVEGACIÓN MÓVIL
   ========================================================================== */
function initMobileNavigation() {
  const toggleBtn = document.getElementById('mobileMenuToggle');
  const mainNav = document.getElementById('mainNav');

  if (!toggleBtn || !mainNav) return;

  toggleBtn.addEventListener('click', () => {
    mainNav.classList.toggle('active');
  });

  // Cerrar al hacer clic en un enlace
  const links = mainNav.querySelectorAll('.nav-link, .dropdown-item');
  links.forEach(l => {
    l.addEventListener('click', () => {
      mainNav.classList.remove('active');
    });
  });
}


/* ==========================================================================
   8. FILTRO CATEGORIZADO DE RESEÑAS DE GOOGLE
   ========================================================================== */
function initReviewsFilter() {
  const revTabs = document.querySelectorAll('.rev-tab');
  const reviewCards = document.querySelectorAll('#reviewsGrid .google-card');
  if (!revTabs.length || !reviewCards.length) return;

  revTabs.forEach(tab => {
    tab.addEventListener('click', () => {
      revTabs.forEach(t => t.classList.remove('active'));
      tab.classList.add('active');
      const filter = tab.getAttribute('data-rev-filter');

      reviewCards.forEach(card => {
        const cat = card.getAttribute('data-category') || '';
        if (filter === 'all' || cat.includes(filter)) {
          card.style.display = 'flex';
          card.style.animation = 'fadeIn 0.3s ease';
        } else {
          card.style.display = 'none';
        }
      });
    });
  });
}

/* ==========================================================================
   9. ACCESIBILIDAD & NAVEGACIÓN POR TECLADO
   ========================================================================== */
function initAccessibility() {
  // Mega-menú accesible con teclado y foco
  const megaParents = document.querySelectorAll('.has-megamenu');
  megaParents.forEach(parent => {
    const trigger = parent.querySelector('a');
    if (!trigger) return;

    trigger.setAttribute('aria-haspopup', 'true');
    trigger.setAttribute('aria-expanded', 'false');

    parent.addEventListener('mouseenter', () => {
      trigger.setAttribute('aria-expanded', 'true');
    });
    parent.addEventListener('mouseleave', () => {
      trigger.setAttribute('aria-expanded', 'false');
    });
    parent.addEventListener('focusin', () => {
      trigger.setAttribute('aria-expanded', 'true');
    });
    parent.addEventListener('focusout', (e) => {
      if (!parent.contains(e.relatedTarget)) {
        trigger.setAttribute('aria-expanded', 'false');
      }
    });
  });

  // Cerrar modal o menú con tecla Escape
  document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') {
      const modal = document.getElementById('quoteModal');
      if (modal && modal.classList.contains('active')) {
        modal.classList.remove('active');
      }
      const nav = document.getElementById('mainNav');
      if (nav && nav.classList.contains('active')) {
        nav.classList.remove('active');
      }
    }
  });
}
