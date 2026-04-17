import factory

from events.models import ApiKey, Event


class EventFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Event

    source = factory.Sequence(lambda n: f"source-{n}")
    event_type = factory.Sequence(lambda n: f"test.event.{n}")
    raw_payload = factory.LazyFunction(lambda: {"message": "test event"})


class ApiKeyFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = ApiKey

    name = factory.Sequence(lambda n: f"test-key-{n}")
