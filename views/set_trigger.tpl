<!DOCTYPE html>
<html lang="en">
  <head>
    <meta charset="utf-8">
    <meta http-equiv="X-UA-Compatible" content="IE=edge">
    <meta name="viewport" content="width=device-width, initial-scale=1">

    <title>Session Test - Set trigger</title>

  </head>
  <body>
    <h1>Session Test - Set trigger</h1>

    <form action="/submit-trigger" method="POST">
      <input type="hidden" name="csrf_token" value="{{ csrf_token }}"></input>
      <label for="nameInput">Name:</label>
      <input type="text" name="trigger" id="nameInput" placeholder="Beyoncé Knowles"></input>
      <button type="submit" name="answer" class="btn btn-default">Submit</button>
   </form>
  </body>
</html>
