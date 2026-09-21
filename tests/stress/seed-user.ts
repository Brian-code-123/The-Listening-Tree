import { createUser } from '../support/users';
import { closeDb } from '../support/db';

const baseURL = process.env.STRESS_BASE_URL || 'http://127.0.0.1:5100';

createUser(baseURL, 'stress')
  .then((u) => console.log(JSON.stringify(u)))
  .finally(closeDb);
