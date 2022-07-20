# storefulfillment

## Steps to deploy
1.  Clone this repo
2.  cd into storefulfillment directory
3.  Build docker/container image by running the following command:  gcloud builds submit --tag gcr.io/{MY-PROJECT-ID}/storefulfillment
4.  In GCP, create a service in Cloud Run

![image](https://user-images.githubusercontent.com/95083111/180077623-8b01b1af-d130-49ba-a00d-59f3cf6166e9.png)

5.  Once service is created, a url will be displayed.  Pasting this into the browser and adding /docs will allow you to see the FastAPI documentation for the API.  e.g. https://storefulfillment-ykh62gqhtq-lz.a.run.app/docs

![image](https://user-images.githubusercontent.com/95083111/180078775-3ba331b7-2ffb-47c7-bcd3-2f1a55abc450.png)


