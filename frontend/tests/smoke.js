// Run with Playwright CLI against a sample-enabled build connected to the demo backend.
async (page) => {
  const origin = new URL(page.url()).origin;
  const errors = [];
  page.on('pageerror', error => errors.push(error.message));
  const heading = name => page.getByRole('heading', { name, exact: true });
  const button = name => page.getByRole('button', { name, exact: true });

  await page.emulateMedia({ reducedMotion: 'reduce' });
  await page.setViewportSize({ width: 375, height: 800 });
  await page.goto(origin);
  await heading('Every Wrong Answer Has a Story.').waitFor();
  await button('Next scene').click();
  if (await page.evaluate(() => document.documentElement.scrollWidth > window.innerWidth)) {
    throw new Error('The landing page overflows on a phone.');
  }

  await page.goto(origin + '/assessment');
  await heading('Welcome Back, Teacher!').waitFor();
  await page.getByLabel('Email', { exact: true }).fill('teacher@mindtrace.demo');
  await page.getByLabel('Password', { exact: true }).fill('demo1234');
  await button('Sign In').click();
  await heading('Welcome to your workspace.').waitFor();
  await page.reload();
  await heading('Welcome to your workspace.').waitFor();
  await button('Sign out').click();
  await heading('Welcome Back, Teacher!').waitFor();

  await page.goto(origin + '/student');
  await heading('Welcome Back, Learner!').waitFor();
  await page.getByLabel('Student code').fill('7A-01');
  await page.getByLabel('PIN', { exact: true }).fill('1111');
  await button('Sign In').click();
  await heading('Hello, Aarav!').waitFor();
  await page.getByRole('heading', { name: /^Latest assessment/ }).waitFor();
  await heading('Concept to revisit').waitFor();
  if (await page.getByRole('navigation', { name: 'Main navigation' }).count()) {
    throw new Error('Teacher navigation appeared in the student home.');
  }
  await button('Sign out').click();
  await heading('Welcome Back, Learner!').waitFor();

  await page.goto(origin + '/login?role=teacher');
  await button('Explore sample workspace').click();
  await page.getByText('Mock mode · sample data, not live').waitFor();
  await heading('Good morning, Alex.').waitFor();
  await button('Exit sample').click();
  await heading('Welcome Back, Teacher!').waitFor();
  if (errors.length) throw new Error(errors.join('\n'));
  return 'Landing, teacher sign-in and refresh, student results, and sample workspace passed.';
};
