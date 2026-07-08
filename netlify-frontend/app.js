import { createLabelCreatorApp } from './js/labelCreatorApp.js';
import { formatFetchError } from './js/utils.js';

createLabelCreatorApp().init();

export { createLabelCreatorApp, formatFetchError };
