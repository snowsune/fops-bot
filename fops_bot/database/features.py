from .database import Session
from sqlalchemy import Column, Integer, String, Boolean, Text, ForeignKey
from sqlalchemy.orm import relationship


# Guild and Feature Models
class Guild(Base):
    __tablename__ = "guilds"

    id = Column(Integer, primary_key=True)
    guild_id = Column(String, unique=True, nullable=False)
    name = Column(String, nullable=False)
    features = relationship(
        "Feature", back_populates="guild", cascade="all, delete-orphan"
    )

    def add_or_update_feature(self, session, feature_name, enabled=True, data=None):
        feature = next((f for f in self.features if f.name == feature_name), None)
        if feature:
            feature.enabled = enabled
            feature.data = data
        else:
            feature = Feature(name=feature_name, enabled=enabled, data=data, guild=self)
            self.features.append(feature)
        session.commit()

    def get_all_features(self):
        return {feature.name: feature.enabled for feature in self.features}


class Feature(Base):
    __tablename__ = "features"

    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)
    enabled = Column(Boolean, default=True)
    data = Column(Text)  # JSON or stringified list (e.g., channels/users)
    guild_id = Column(Integer, ForeignKey("guilds.id"))
    guild = relationship("Guild", back_populates="features")


# Utility Functions
def get_or_create_guild(session, guild_id, guild_name):
    guild = session.query(Guild).filter_by(guild_id=guild_id).first()
    if not guild:
        guild = Guild(guild_id=guild_id, name=guild_name)
        session.add(guild)
        session.commit()
    return guild


def set_feature(session, guild_id, feature_name, enabled=True, data=None):
    guild = get_or_create_guild(session, guild_id, "Unknown Guild")
    guild.add_or_update_feature(session, feature_name, enabled, data)


def get_all_features(session, guild_id):
    guild = session.query(Guild).filter_by(guild_id=guild_id).first()
    if not guild:
        return {}
    return guild.get_all_features()
